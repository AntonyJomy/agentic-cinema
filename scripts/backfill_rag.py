#!/usr/bin/env python3
"""
scripts/backfill_rag.py

Seed the semantic research vector index from existing entity_research_cache entries.

Usage:
    python scripts/backfill_rag.py
    python scripts/backfill_rag.py --dry-run
    python scripts/backfill_rag.py --limit 50
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from api.settings import firestore_database, firestore_project
from research.cache import entity_cache_key, is_cacheable_research
from research.retrieval import index_research_result
from schemas.entities import EntityType
from schemas.research_result import ResearchResult

logger = logging.getLogger("backfill_rag")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

CACHE_COLLECTION = "entity_research_cache"


def _load_cache_entries(limit: int | None) -> list[dict]:
    backend = os.getenv("RESEARCH_CACHE_BACKEND", "auto").strip().lower()
    if backend == "memory":
        from research.store import get_research_cache

        cache = get_research_cache()
        with cache._lock:  # type: ignore[attr-defined]
            entries = list(cache._entries.values())  # type: ignore[attr-defined]
        return entries[:limit] if limit else entries

    from google.cloud import firestore

    client = firestore.Client(
        project=firestore_project(),
        database=firestore_database(),
    )
    query = client.collection(CACHE_COLLECTION)
    snaps = query.stream()
    entries: list[dict] = []
    for snap in snaps:
        entries.append(snap.to_dict() or {})
        if limit and len(entries) >= limit:
            break
    return entries


def backfill(*, dry_run: bool, limit: int | None) -> int:
    entries = _load_cache_entries(limit)
    indexed = 0
    skipped = 0

    for payload in entries:
        entity_type_raw = payload.get("entity_type")
        entity_name = payload.get("entity_name") or ""
        if not entity_type_raw or not entity_name:
            skipped += 1
            continue
        try:
            entity_type = EntityType(entity_type_raw)
            result = ResearchResult.model_validate(payload.get("research_result") or {})
        except Exception:
            skipped += 1
            continue
        if not is_cacheable_research(result):
            skipped += 1
            continue

        cache_key = payload.get("cache_key") or entity_cache_key(entity_type, entity_name)
        if dry_run:
            logger.info("Would index %s (%s)", cache_key, entity_name)
        else:
            index_research_result(
                entity_type,
                entity_name,
                result,
                context=payload.get("context_snippet"),
            )
            logger.info("Indexed %s (%s)", cache_key, entity_name)
        indexed += 1

    logger.info("Backfill complete: indexed=%s skipped=%s dry_run=%s", indexed, skipped, dry_run)
    if not dry_run:
        logger.info(
            "If Firestore native vector search is enabled, ensure a composite index exists, e.g.:\n"
            "  gcloud firestore indexes composite create \\\n"
            "    --collection-group=entity_research_vectors \\\n"
            "    --query-scope=COLLECTION \\\n"
            "    --field-config field-path=entity_type,order=ASCENDING \\\n"
            "    --field-config vector-config='{\"dimension\":\"1536\",\"flat\": \"{}\"}',field-path=embedding"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill RAG vector index from research cache")
    parser.add_argument("--dry-run", action="store_true", help="List entries without indexing")
    parser.add_argument("--limit", type=int, default=None, help="Max cache entries to process")
    args = parser.parse_args()
    return backfill(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
