"""
research/store.py

Persistence for entity research cache entries.

Backends:
  - firestore: entity_research_cache collection
  - memory: process-local dict (tests and Firestore-unavailable dev)
  - auto: try Firestore, fall back to memory
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Protocol

from api.settings import firestore_database, firestore_project
from research.cache import (
    entity_cache_key,
    is_cache_entry_fresh,
    is_cacheable_research,
)
from schemas.entities import EntityType
from schemas.research_result import ResearchResult

logger = logging.getLogger("agentic_cinema.research_cache")

COLLECTION = "entity_research_cache"


class ResearchCache(Protocol):
    def lookup(self, entity_type: EntityType, name: str) -> ResearchResult | None: ...

    def upsert(
        self,
        entity_type: EntityType,
        name: str,
        result: ResearchResult,
        *,
        source_run_id: str | None = None,
    ) -> None: ...

    def clear(self) -> None: ...


class MemoryResearchCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}

    def lookup(self, entity_type: EntityType, name: str) -> ResearchResult | None:
        key = entity_cache_key(entity_type, name)
        with self._lock:
            payload = self._entries.get(key)
        if not payload:
            return None
        if not is_cache_entry_fresh(payload.get("indexed_at")):
            return None
        try:
            result = ResearchResult.model_validate(payload["research_result"])
        except Exception:
            logger.warning("Skipping corrupt in-memory research cache entry %s", key)
            return None
        return result if is_cacheable_research(result) else None

    def upsert(
        self,
        entity_type: EntityType,
        name: str,
        result: ResearchResult,
        *,
        source_run_id: str | None = None,
    ) -> None:
        if not is_cacheable_research(result):
            return
        key = entity_cache_key(entity_type, name)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._entries[key] = {
                "cache_key": key,
                "entity_type": entity_type.value,
                "entity_name": name,
                "research_result": result.model_dump(mode="json"),
                "indexed_at": now,
                "confidence": result.confidence,
                "source_run_id": source_run_id,
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class FirestoreResearchCache:
    def __init__(self, client) -> None:
        self._collection = client.collection(COLLECTION)

    def lookup(self, entity_type: EntityType, name: str) -> ResearchResult | None:
        key = entity_cache_key(entity_type, name)
        snap = self._collection.document(key).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        if not is_cache_entry_fresh(data.get("indexed_at")):
            return None
        try:
            result = ResearchResult.model_validate(data.get("research_result") or {})
        except Exception:
            logger.warning("Skipping corrupt Firestore research cache entry %s", key)
            return None
        return result if is_cacheable_research(result) else None

    def upsert(
        self,
        entity_type: EntityType,
        name: str,
        result: ResearchResult,
        *,
        source_run_id: str | None = None,
    ) -> None:
        if not is_cacheable_research(result):
            return
        key = entity_cache_key(entity_type, name)
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "cache_key": key,
            "entity_type": entity_type.value,
            "entity_name": name,
            "research_result": result.model_dump(mode="json"),
            "indexed_at": now,
            "confidence": result.confidence,
            "source_run_id": source_run_id,
        }
        self._collection.document(key).set(payload)

    def clear(self) -> None:
        raise NotImplementedError("Refusing to wipe the Firestore research cache")


_cache: ResearchCache | None = None
_cache_lock = threading.Lock()


def _research_cache_backend() -> str:
    return os.getenv("RESEARCH_CACHE_BACKEND", "auto").strip().lower()


def _try_firestore_cache() -> ResearchCache | None:
    try:
        from google.cloud import firestore

        client = firestore.Client(
            project=firestore_project(),
            database=firestore_database(),
        )
        logger.info(
            "Using Firestore research cache (%s / %s)",
            firestore_project(),
            firestore_database(),
        )
        return FirestoreResearchCache(client)
    except Exception:
        logger.warning(
            "Firestore research cache unavailable; using in-memory cache.",
            exc_info=True,
        )
        return None


def get_research_cache() -> ResearchCache:
    global _cache
    if _cache is not None:
        return _cache
    with _cache_lock:
        if _cache is not None:
            return _cache
        backend = _research_cache_backend()
        if backend == "memory":
            _cache = MemoryResearchCache()
            logger.info("Using in-memory research cache (RESEARCH_CACHE_BACKEND=memory)")
        elif backend == "firestore":
            store = _try_firestore_cache()
            if store is None:
                raise RuntimeError(
                    "RESEARCH_CACHE_BACKEND=firestore but Firestore is unavailable"
                )
            _cache = store
        else:
            _cache = _try_firestore_cache() or MemoryResearchCache()
        return _cache


def reset_research_cache_for_tests() -> MemoryResearchCache:
    global _cache
    with _cache_lock:
        _cache = MemoryResearchCache()
        return _cache
