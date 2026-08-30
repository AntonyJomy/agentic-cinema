"""
research/vector_store.py

Vector index for semantic research retrieval.

Backends:
  - memory: in-process cosine search (tests and dev)
  - firestore: entity_research_vectors collection with brute-force search
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
from research.rag_config import research_rag_top_k
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
        stored_embedding = embedding
        try:
            from google.cloud.firestore_v1.vector import Vector

            stored_embedding = Vector(embedding)
        except Exception:
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
        self._collection.document(key).set(payload)

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
            return hits[:limit]
        except Exception:
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
