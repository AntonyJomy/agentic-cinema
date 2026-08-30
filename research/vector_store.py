"""
research/vector_store.py

Vector index for semantic research retrieval.

Backends:
  - memory: in-process cosine search (tests and dev)
  - firestore: entity_research_vectors collection with native vector search
  - auto: try Firestore, fall back to memory
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from api.settings import firestore_database, firestore_project
from research.cache import entity_cache_key, is_cache_entry_fresh
from research.embeddings import cosine_similarity
from research.rag_config import research_rag_top_k, research_embedding_dimensionality
from schemas.entities import EntityType
from schemas.research_result import ResearchResult

logger = logging.getLogger("agentic_cinema.research_rag")

COLLECTION = "entity_research_vectors"


@dataclass(frozen=True)
class VectorSearchHit:
    score: float
    cache_key: str
    entity_name: str
    entity_type: str
    research_result: ResearchResult
    context_snippet: str | None = None


class ResearchVectorStore(Protocol):
    def upsert(
        self,
        entity_type: EntityType,
        name: str,
        embedding: list[float],
        result: ResearchResult,
        *,
        context: str | None = None,
    ) -> None: ...

    def search(
        self,
        entity_type: EntityType,
        query_embedding: list[float],
        *,
        top_k: int | None = None,
        exclude_cache_key: str | None = None,
    ) -> list[VectorSearchHit]: ...

    def clear(self) -> None: ...


class MemoryResearchVectorStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}

    def upsert(
        self,
        entity_type: EntityType,
        name: str,
        embedding: list[float],
        result: ResearchResult,
        *,
        context: str | None = None,
    ) -> None:
        key = entity_cache_key(entity_type, name)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._entries[key] = {
                "cache_key": key,
                "entity_type": entity_type.value,
                "entity_name": name,
                "embedding": embedding,
                "research_result": result.model_dump(mode="json"),
                "context_snippet": (context or "")[:500] or None,
                "indexed_at": now,
            }

    def search(
        self,
        entity_type: EntityType,
        query_embedding: list[float],
        *,
        top_k: int | None = None,
        exclude_cache_key: str | None = None,
    ) -> list[VectorSearchHit]:
        limit = top_k or research_rag_top_k()
        hits: list[VectorSearchHit] = []
        with self._lock:
            entries = list(self._entries.values())
        for payload in entries:
            if payload.get("entity_type") != entity_type.value:
                continue
            cache_key = payload.get("cache_key") or ""
            if exclude_cache_key and cache_key == exclude_cache_key:
                continue
            if not is_cache_entry_fresh(payload.get("indexed_at")):
                continue
            embedding = payload.get("embedding") or []
            score = cosine_similarity(query_embedding, embedding)
            try:
                result = ResearchResult.model_validate(payload.get("research_result") or {})
            except Exception:
                logger.warning("Skipping corrupt vector entry %s", cache_key)
                continue
            hits.append(
                VectorSearchHit(
                    score=score,
                    cache_key=cache_key,
                    entity_name=payload.get("entity_name") or result.entity_name,
                    entity_type=payload.get("entity_type") or result.entity_type.value,
                    research_result=result,
                    context_snippet=payload.get("context_snippet"),
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def _embedding_values(raw) -> list[float]:
    if raw is None:
        return []
    values = getattr(raw, "values", None)
    if values is not None:
        return [float(v) for v in values]
    return [float(v) for v in raw]


def _cosine_score_from_distance(distance: float | None) -> float:
    if distance is None:
        return 0.0
    # Firestore COSINE distance for normalized vectors is typically 1 - cosine_similarity.
    return max(0.0, min(1.0, 1.0 - float(distance)))


class FirestoreResearchVectorStore:
    def __init__(self, client) -> None:
        self._collection = client.collection(COLLECTION)
        self._use_native_vector_search = os.getenv(
            "RESEARCH_RAG_FIRESTORE_NATIVE", "true"
        ).strip().lower() not in {"0", "false", "no", "off"}

    def upsert(
        self,
        entity_type: EntityType,
        name: str,
        embedding: list[float],
        result: ResearchResult,
        *,
        context: str | None = None,
    ) -> None:
        key = entity_cache_key(entity_type, name)
        now = datetime.now(timezone.utc).isoformat()
        
        # Validate embedding dimensions before attempting to store
        expected_dim = research_embedding_dimensionality()
        if len(embedding) != expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected_dim}, got {len(embedding)}. "
                f"Cannot store in Firestore (max 2048 dimensions)."
            )
        
        # Store as Vector for native vector search support
        stored_embedding = embedding
        try:
            from google.cloud.firestore_v1.vector import Vector
            stored_embedding = Vector(embedding)
        except Exception as e:
            # Re-raise if this is a dimension error (likely the root cause)
            if "dimension" in str(e).lower():
                logger.error("Firestore Vector dimension error for %s: %s", key, e)
                raise
            # Fall back to list if Vector import fails for other reasons
            logger.warning("Vector import failed, storing as list: %s", e)
            stored_embedding = embedding
        
        payload = {
            "cache_key": key,
            "entity_type": entity_type.value,
            "entity_name": name,
            "embedding": stored_embedding,
            "research_result": result.model_dump(mode="json"),
            "context_snippet": (context or "")[:500] or None,
            "indexed_at": now,
        }
        
        try:
            self._collection.document(key).set(payload)
            logger.debug("Successfully indexed vector for %s (%d dims)", key, len(embedding))
        except Exception as e:
            # Surface dimension errors explicitly
            error_msg = str(e).lower()
            if "dimension" in error_msg or "2048" in error_msg or "invalid" in error_msg:
                logger.error(
                    "Failed to upsert vector for %s: %s. "
                    "Embedding has %d dimensions, Firestore supports max 2048.",
                    key,
                    e,
                    len(embedding),
                )
                raise RuntimeError(
                    f"Firestore vector upsert failed for {name}: {e}. "
                    f"Check embedding dimensionality ({len(embedding)} dims)."
                ) from e
            # Re-raise other errors
            logger.error("Firestore upsert failed for %s: %s", key, e)
            raise

    def search(
        self,
        entity_type: EntityType,
        query_embedding: list[float],
        *,
        top_k: int | None = None,
        exclude_cache_key: str | None = None,
    ) -> list[VectorSearchHit]:
        limit = top_k or research_rag_top_k()
        if self._use_native_vector_search:
            native_hits = self._search_native(
                entity_type,
                query_embedding,
                limit=limit,
                exclude_cache_key=exclude_cache_key,
            )
            if native_hits is not None:
                return native_hits
        return self._search_brute_force(
            entity_type,
            query_embedding,
            limit=limit,
            exclude_cache_key=exclude_cache_key,
        )

    def _search_native(
        self,
        entity_type: EntityType,
        query_embedding: list[float],
        *,
        limit: int,
        exclude_cache_key: str | None,
    ) -> list[VectorSearchHit] | None:
        try:
            from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
            from google.cloud.firestore_v1.vector import Vector

            # Validate query dimensions
            expected_dim = research_embedding_dimensionality()
            if len(query_embedding) != expected_dim:
                logger.error(
                    "Query embedding dimension mismatch: expected %d, got %d. "
                    "Native vector search will fail.",
                    expected_dim,
                    len(query_embedding),
                )
                return None

            vector_query = (
                self._collection.where("entity_type", "==", entity_type.value)
                .find_nearest(
                    vector_field="embedding",
                    query_vector=Vector(query_embedding),
                    distance_measure=DistanceMeasure.COSINE,
                    limit=max(limit + 3, limit),
                    distance_result_field="vector_distance",
                )
            )
            hits: list[VectorSearchHit] = []
            for snap in vector_query.stream():
                payload = snap.to_dict() or {}
                cache_key = payload.get("cache_key") or snap.id
                if exclude_cache_key and cache_key == exclude_cache_key:
                    continue
                if not is_cache_entry_fresh(payload.get("indexed_at")):
                    continue
                score = _cosine_score_from_distance(payload.get("vector_distance"))
                try:
                    result = ResearchResult.model_validate(payload.get("research_result") or {})
                except Exception:
                    logger.warning("Skipping corrupt Firestore vector entry %s", cache_key)
                    continue
                hits.append(
                    VectorSearchHit(
                        score=score,
                        cache_key=cache_key,
                        entity_name=payload.get("entity_name") or result.entity_name,
                        entity_type=payload.get("entity_type") or result.entity_type.value,
                        research_result=result,
                        context_snippet=payload.get("context_snippet"),
                    )
                )
            hits.sort(key=lambda hit: hit.score, reverse=True)
            logger.debug(
                "Native vector search returned %d hits for %s",
                len(hits[:limit]),
                entity_type.value,
            )
            return hits[:limit]
        except Exception as e:
            # Log dimension-related errors more explicitly
            error_msg = str(e).lower()
            if "dimension" in error_msg or "2048" in error_msg or "invalid" in error_msg:
                logger.error(
                    "Firestore native vector search failed due to dimension mismatch: %s. "
                    "Query has %d dimensions. Falling back to brute-force scan.",
                    e,
                    len(query_embedding),
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Firestore native vector search unavailable; using brute-force scan.",
                    exc_info=True,
                )
            return None

    def _search_brute_force(
        self,
        entity_type: EntityType,
        query_embedding: list[float],
        *,
        limit: int,
        exclude_cache_key: str | None,
    ) -> list[VectorSearchHit]:
        hits: list[VectorSearchHit] = []
        for snap in self._collection.where("entity_type", "==", entity_type.value).stream():
            payload = snap.to_dict() or {}
            cache_key = payload.get("cache_key") or snap.id
            if exclude_cache_key and cache_key == exclude_cache_key:
                continue
            if not is_cache_entry_fresh(payload.get("indexed_at")):
                continue
            embedding = _embedding_values(payload.get("embedding"))
            score = cosine_similarity(query_embedding, embedding)
            try:
                result = ResearchResult.model_validate(payload.get("research_result") or {})
            except Exception:
                logger.warning("Skipping corrupt Firestore vector entry %s", cache_key)
                continue
            hits.append(
                VectorSearchHit(
                    score=score,
                    cache_key=cache_key,
                    entity_name=payload.get("entity_name") or result.entity_name,
                    entity_type=payload.get("entity_type") or result.entity_type.value,
                    research_result=result,
                    context_snippet=payload.get("context_snippet"),
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def clear(self) -> None:
        raise NotImplementedError("Refusing to wipe the Firestore research vector index")


_store: ResearchVectorStore | None = None
_store_lock = threading.Lock()


def _try_firestore_store() -> ResearchVectorStore | None:
    try:
        from google.cloud import firestore

        client = firestore.Client(
            project=firestore_project(),
            database=firestore_database(),
        )
        logger.info(
            "Using Firestore research vector store (%s / %s)",
            firestore_project(),
            firestore_database(),
        )
        return FirestoreResearchVectorStore(client)
    except Exception:
        logger.warning(
            "Firestore research vector store unavailable; using in-memory store.",
            exc_info=True,
        )
        return None


def get_research_vector_store() -> ResearchVectorStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        backend = os.getenv("RESEARCH_RAG_BACKEND", "auto").strip().lower()
        if backend == "memory":
            _store = MemoryResearchVectorStore()
            logger.info("Using in-memory research vector store (RESEARCH_RAG_BACKEND=memory)")
        elif backend == "firestore":
            store = _try_firestore_store()
            if store is None:
                raise RuntimeError(
                    "RESEARCH_RAG_BACKEND=firestore but Firestore is unavailable"
                )
            _store = store
        else:
            _store = _try_firestore_store() or MemoryResearchVectorStore()
        return _store


def reset_research_vector_store_for_tests() -> MemoryResearchVectorStore:
    global _store
    with _store_lock:
        _store = MemoryResearchVectorStore()
        return _store
