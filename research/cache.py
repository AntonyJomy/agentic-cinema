"""
research/cache.py

Exact-match research cache keys and eligibility rules.

Cache key: entity_type + normalized entity name (same normalizer as grounding).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from gatekeeper.deterministic_grounding import normalize_grounding_text
from schemas.entities import Entity, EntityType
from schemas.research_result import ResearchResult, ResearchStatus


def research_cache_enabled() -> bool:
    raw = os.getenv("RESEARCH_CACHE_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def research_cache_ttl_days() -> int:
    raw = os.getenv("RESEARCH_CACHE_TTL_DAYS", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 30
    return max(1, value)


def research_cache_min_confidence() -> float:
    raw = os.getenv("RESEARCH_CACHE_MIN_CONFIDENCE", "0.75").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 0.75
    return min(1.0, max(0.0, value))


def entity_cache_key(entity_type: EntityType | str, name: str) -> str:
    """Stable lookup key for cross-run and within-run deduplication."""
    type_value = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
    normalized = normalize_grounding_text(name)
    if not normalized:
        normalized = "_unnamed"
    return f"{type_value}:{normalized}"


def is_cacheable_research(result: ResearchResult | None) -> bool:
    """Only reuse successful, sufficiently confident research."""
    if result is None:
        return False
    if result.status != ResearchStatus.SUCCESS:
        return False
    if result.confidence < research_cache_min_confidence():
        return False
    if not (result.finding or "").strip():
        return False
    return True


def parse_cache_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_cache_entry_fresh(indexed_at: str | None) -> bool:
    parsed = parse_cache_timestamp(indexed_at)
    if parsed is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=research_cache_ttl_days())
    return parsed >= cutoff


def adapt_research_for_entity(cached: ResearchResult, entity: Entity) -> ResearchResult:
    """Copy cached research onto the current entity_id for downstream scoring."""
    return cached.model_copy(
        update={
            "entity_id": entity.entity_id,
            "entity_name": entity.name,
            "entity_type": entity.entity_type,
        }
    )
