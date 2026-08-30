"""
tests/test_research_cache.py

Unit tests for exact-match entity research cache (no Parallel / Gemini).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gatekeeper.deterministic_grounding import normalize_grounding_text
from research.cache import (
    adapt_research_for_entity,
    entity_cache_key,
    is_cache_entry_fresh,
    is_cacheable_research,
    research_cache_enabled,
)
from research.store import MemoryResearchCache, reset_research_cache_for_tests
from schemas.entities import Entity, EntityType, ScriptLocation
from schemas.research_result import Citation, ResearchResult, ResearchStatus


def _sample_result(*, confidence: float = 0.9) -> ResearchResult:
    return ResearchResult(
        entity_id=None,
        entity_name="McDonald's",
        entity_type=EntityType.BUSINESS,
        finding="Real global fast-food chain.",
        confidence=confidence,
        citations=[
            Citation(
                source_url="https://example.com/mcd",
                summary="Corporate site",
            )
        ],
        status=ResearchStatus.SUCCESS,
    )


def _sample_entity(entity_id: str = "ent-1") -> Entity:
    return Entity(
        entity_id=entity_id,
        name="McDonald's",
        entity_type=EntityType.BUSINESS,
        risk_category="business_location",
        context="A storefront on Main Street.",
        location=ScriptLocation(page_number=1, scene_number=1, line_excerpt="INT. MCDONALD'S"),
        confidence=0.9,
        requires_human_review=True,
    )


def test_entity_cache_key_normalizes_name():
    key_a = entity_cache_key(EntityType.BUSINESS, "McDonald's")
    key_b = entity_cache_key(EntityType.BUSINESS, "  mcdonald's ")
    assert key_a == key_b == "business:mcdonald's"


def test_is_cacheable_research_requires_success_and_confidence():
    assert is_cacheable_research(_sample_result()) is True
    assert is_cacheable_research(_sample_result(confidence=0.5)) is False
    failed = _sample_result().model_copy(update={"status": ResearchStatus.TOOL_FAILURE})
    assert is_cacheable_research(failed) is False


def test_memory_cache_hit_miss_and_ttl(monkeypatch):
    monkeypatch.setenv("RESEARCH_CACHE_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_CACHE_TTL_DAYS", "30")
    cache = reset_research_cache_for_tests()
    result = _sample_result()

    assert cache.lookup(EntityType.BUSINESS, "McDonald's") is None
    cache.upsert(EntityType.BUSINESS, "McDonald's", result)
    hit = cache.lookup(EntityType.BUSINESS, "McDonald's")
    assert hit is not None
    assert hit.finding == result.finding

    stale = datetime.now(timezone.utc) - timedelta(days=31)
    key = entity_cache_key(EntityType.BUSINESS, "McDonald's")
    with cache._lock:
        cache._entries[key]["indexed_at"] = stale.isoformat()
    assert cache.lookup(EntityType.BUSINESS, "McDonald's") is None


def test_adapt_research_for_entity_sets_entity_id():
    entity = _sample_entity("ent-99")
    adapted = adapt_research_for_entity(_sample_result(), entity)
    assert adapted.entity_id == "ent-99"
    assert adapted.entity_name == "McDonald's"


def test_cache_disabled_via_env(monkeypatch):
    monkeypatch.setenv("RESEARCH_CACHE_ENABLED", "false")
    assert research_cache_enabled() is False


def test_normalize_grounding_text_used_for_keys():
    assert normalize_grounding_text("McDonald’s") == normalize_grounding_text("McDonald's")
