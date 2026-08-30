#!/usr/bin/env python3
"""
scripts/migrate_vector_dims.py

Migrate existing vector embeddings to new dimensionality (1536) by clearing
and re-indexing from the research cache.

This script:
1. Deletes all documents in the entity_research_vectors collection
2. Re-generates embeddings at the new dimensionality (1536)
3. Re-indexes all cacheable research from entity_research_cache

Usage:
    python scripts/migrate_vector_dims.py
    python scripts/migrate_vector_dims.py --dry-run
    python scripts/migrate_vector_dims.py --limit 50

⚠️  WARNING: This will delete ALL existing vectors in the collection.
    Make sure you have set RESEARCH_EMBEDDING_DIMENSIONALITY=1536 in your .env
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
from research.embeddings import embed_text
from research.rag_config import research_embedding_dimensionality
from research.vector_store import COLLECTION, get_research_vector_store
from schemas.entities import EntityType
from schemas.research_result import ResearchResult

logger = logging.getLogger("migrate_vector_dims")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

CACHE_COLLECTION = "entity_research_cache"


def _get_firestore_client():
    """Get Firestore client for direct collection operations."""
    from google.cloud import firestore

    return firestore.Client(
        project=firestore_project(),
        database=firestore_database(),
    )


def _clear_vector_collection(client, dry_run: bool) -> int:
    """Delete all documents in the vector collection."""
    collection = client.collection(COLLECTION)
    deleted = 0
    
    logger.info("Scanning %s collection for deletion...", COLLECTION)
    docs = collection.stream()
    
    batch = client.batch()
    batch_size = 0
    max_batch_size = 500  # Firestore batch write limit
    
    for doc in docs:
        if dry_run:
            logger.debug("Would delete document: %s", doc.id)
        else:
            batch.delete(doc.reference)
            batch_size += 1
            
            # Commit batch when it reaches max size
            if batch_size >= max_batch_size:
                batch.commit()
                logger.info("Deleted batch of %d documents", batch_size)
                batch = client.batch()
                batch_size = 0
        
        deleted += 1
    
    # Commit remaining documents
    if not dry_run and batch_size > 0:
        batch.commit()
        logger.info("Deleted final batch of %d documents", batch_size)
    
    return deleted


def _load_cache_entries(limit: int | None) -> list[dict]:
    """Load research cache entries for re-indexing."""
    backend = os.getenv("RESEARCH_CACHE_BACKEND", "auto").strip().lower()
    if backend == "memory":
        from research.store import get_research_cache

        cache = get_research_cache()
        with cache._lock:  # type: ignore[attr-defined]
            entries = list(cache._entries.values())  # type: ignore[attr-defined]
        return entries[:limit] if limit else entries

    client = _get_firestore_client()
    query = client.collection(CACHE_COLLECTION)
    snaps = query.stream()
    entries: list[dict] = []
    for snap in snaps:
        entries.append(snap.to_dict() or {})
        if limit and len(entries) >= limit:
            break
    return entries


def migrate(*, dry_run: bool, limit: int | None, skip_clear: bool = False) -> int:
    """
    Migrate vector collection to new dimensionality.
    
    Args:
        dry_run: If True, only log what would be done
        limit: Max cache entries to process (None for all)
        skip_clear: If True, skip the deletion step (for testing)
    
    Returns:
        Exit code (0 for success)
    """
    target_dim = research_embedding_dimensionality()
    logger.info("=" * 80)
    logger.info("Vector Dimensionality Migration")
    logger.info("=" * 80)
    logger.info("Target dimensionality: %d", target_dim)
    logger.info("Dry run: %s", dry_run)
    logger.info("")
    
    if target_dim > 2048:
        logger.error(
            "Target dimensionality %d exceeds Firestore limit of 2048. "
            "Set RESEARCH_EMBEDDING_DIMENSIONALITY to 1536 or lower.",
            target_dim,
        )
        return 1
    
    # Step 1: Clear existing vectors
    if not skip_clear:
        logger.info("Step 1: Clearing existing vector collection")
        logger.info("-" * 80)
        
        if dry_run:
            logger.info("DRY RUN: Would delete all documents from %s", COLLECTION)
            deleted = 0
        else:
            client = _get_firestore_client()
            deleted = _clear_vector_collection(client, dry_run=False)
            logger.info("Deleted %d documents from %s", deleted, COLLECTION)
        
        logger.info("")
    else:
        logger.info("Skipping deletion step (--skip-clear)")
        logger.info("")
    
    # Step 2: Load cache entries
    logger.info("Step 2: Loading research cache entries")
    logger.info("-" * 80)
    entries = _load_cache_entries(limit)
    logger.info("Loaded %d cache entries", len(entries))
    logger.info("")
    
    # Step 3: Re-index with new dimensionality
    logger.info("Step 3: Re-indexing with %d-dimensional embeddings", target_dim)
    logger.info("-" * 80)
    
    indexed = 0
    skipped = 0
    failed = 0
    
    vector_store = get_research_vector_store()
    
    for i, payload in enumerate(entries, start=1):
        entity_type_raw = payload.get("entity_type")
        entity_name = payload.get("entity_name") or ""
        
        if not entity_type_raw or not entity_name:
            skipped += 1
            continue
        
        try:
            entity_type = EntityType(entity_type_raw)
            result = ResearchResult.model_validate(payload.get("research_result") or {})
        except Exception as e:
            logger.warning("Skipping invalid entry %d: %s", i, e)
            skipped += 1
            continue
        
        if not is_cacheable_research(result):
            skipped += 1
            continue
        
        cache_key = payload.get("cache_key") or entity_cache_key(entity_type, entity_name)
        context = payload.get("context_snippet")
        
        if dry_run:
            logger.info("[%d/%d] Would re-index: %s (%s)", i, len(entries), cache_key, entity_name)
            indexed += 1
        else:
            try:
                # Generate new embedding at target dimensionality
                from research.rag_config import build_rag_document_text
                
                document_text = build_rag_document_text(entity_type, entity_name, result, context=context)
                embedding = embed_text(document_text)
                
                # Validate dimensions
                if len(embedding) != target_dim:
                    logger.error(
                        "[%d/%d] Dimension mismatch for %s: expected %d, got %d",
                        i,
                        len(entries),
                        cache_key,
                        target_dim,
                        len(embedding),
                    )
                    failed += 1
                    continue
                
                # Store in vector index
                generic = result.model_copy(update={"entity_id": None})
                vector_store.upsert(
                    entity_type,
                    entity_name,
                    embedding,
                    generic,
                    context=context,
                )
                
                logger.info("[%d/%d] Re-indexed: %s (%s)", i, len(entries), cache_key, entity_name)
                indexed += 1
                
            except Exception as e:
                logger.error("[%d/%d] Failed to re-index %s: %s", i, len(entries), cache_key, e)
                failed += 1
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Migration Summary")
    logger.info("=" * 80)
    logger.info("Successfully indexed: %d", indexed)
    logger.info("Skipped (not cacheable): %d", skipped)
    logger.info("Failed: %d", failed)
    logger.info("Dry run: %s", dry_run)
    logger.info("")
    
    if not dry_run and indexed > 0:
        logger.info(
            "✓ Migration complete! Ensure the Firestore vector index exists:\n"
            "  gcloud firestore indexes composite create \\\n"
            "    --collection-group=entity_research_vectors \\\n"
            "    --query-scope=COLLECTION \\\n"
            "    --field-config field-path=entity_type,order=ASCENDING \\\n"
            "    --field-config vector-config='{\"dimension\":\"%d\",\"flat\": \"{}\"}',field-path=embedding",
            target_dim,
        )
    
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate vector embeddings to new dimensionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would happen
  python scripts/migrate_vector_dims.py --dry-run
  
  # Migrate first 10 entries (for testing)
  python scripts/migrate_vector_dims.py --limit 10
  
  # Full migration
  python scripts/migrate_vector_dims.py
  
  # Re-index without deleting (if collection is already empty)
  python scripts/migrate_vector_dims.py --skip-clear
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max cache entries to process (useful for testing)",
    )
    parser.add_argument(
        "--skip-clear",
        action="store_true",
        help="Skip deletion step (re-index only)",
    )
    args = parser.parse_args()
    
    return migrate(dry_run=args.dry_run, limit=args.limit, skip_clear=args.skip_clear)


if __name__ == "__main__":
    raise SystemExit(main())
