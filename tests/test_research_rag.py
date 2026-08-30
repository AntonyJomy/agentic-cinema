"""
tests/test_research_rag.py

Unit tests for semantic research retrieval (no Parallel / live Gemini).
"""
from __future__ import annotations

import asyncio

import pytest

from research.embeddings import TestEmbeddingProvider, cosine_similarity, reset_embedding_provider_for_tests
from research.metrics import ResearchMetrics, ResearchSource, reset_research_metrics_for_tests
from research.rag_llm import synthesize_rag_result
from research.rag_config import build_rag_document_text, build_rag_query_text
from research.retrieval import index_research_result, retrieve_similar_research
from research.store import reset_research_cache_for_tests
from research.vector_store import reset_research_vector_store_for_tests
from schemas.entities import Entity, EntityType, ScriptLocation
from schemas.research_result import Citation, ResearchResult, ResearchStatus


def _sample_result(
    *,
    name: str = "McDonald's",
    finding: str = "McDonald's is a global fast-food restaurant chain.",
) -> ResearchResult:
    return ResearchResult(
        entity_id=None,
        entity_name=name,
        entity_type=EntityType.BUSINESS,
        finding=finding,
        confidence=0.9,
        citations=[
            Citation(
                source_url="https://example.com/mcd",
                summary="Corporate fast-food chain information",
            )
        ],
        status=ResearchStatus.SUCCESS,
    )


def _sample_entity(
    *,
    entity_id: str = "ent-1",
    name: str = "McDonald's",
    context: str = "INT. FAST FOOD RESTAURANT - DAY",
) -> Entity:
    return Entity(
        entity_id=entity_id,
        name=name,
        entity_type=EntityType.BUSINESS,
        risk_category="business_location",
        context=context,
        location=ScriptLocation(page_number=1, scene_number=1, line_excerpt="INT. MCDONALD'S"),
        confidence=0.9,
        requires_human_review=True,
    )


@pytest.fixture(autouse=True)
def rag_test_env(monkeypatch):
    monkeypatch.setenv("RESEARCH_RAG_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_RAG_BACKEND", "memory")
    monkeypatch.setenv("RESEARCH_EMBEDDING_BACKEND", "test")
    monkeypatch.setenv("RESEARCH_RAG_HIGH_SCORE", "0.85")
    monkeypatch.setenv("RESEARCH_RAG_MEDIUM_SCORE", "0.72")
    monkeypatch.setenv("RESEARCH_RAG_LLM_BACKEND", "test")
    reset_research_cache_for_tests()
    reset_research_vector_store_for_tests()
    reset_embedding_provider_for_tests(TestEmbeddingProvider())
    reset_research_metrics_for_tests()


def test_cosine_similarity_identical_vectors():
    vector = TestEmbeddingProvider().embed("mcdonalds fast food chain restaurant")
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_index_and_high_tier_rag_hit():
    shared_context = (
        "fast food restaurant chain burgers fries corporate branding worldwide"
    )
    indexed = _sample_result(
        name="McDonald's",
        finding="Global fast food restaurant chain burgers fries worldwide corporate branding.",
    )
    index_research_result(
        EntityType.BUSINESS,
        "McDonald's",
        indexed,
        context=shared_context,
    )

    query_entity = _sample_entity(
        name="Mickey D fast food chain",
        context=shared_context,
    )
    match = asyncio.run(retrieve_similar_research(query_entity))
    assert match is not None
    assert match.tier == "high"
    assert match.source_name == "McDonald's"
    assert match.score >= 0.85


def test_medium_tier_rag_hit():
    indexed = _sample_result(name="McDonald's")
    index_research_result(
        EntityType.BUSINESS,
        "McDonald's",
        indexed,
        context="A fast food restaurant on Main Street.",
    )

    query_entity = _sample_entity(
        name="Golden Arches fast food restaurant chain",
        context="Customers order burgers at a fast food chain restaurant.",
    )
    match = asyncio.run(retrieve_similar_research(query_entity))
    assert match is not None
    assert match.tier == "medium"
    assert match.score >= 0.72
    assert match.score < 0.85


def test_exact_name_excluded_from_rag_self_match():
    result = _sample_result()
    index_research_result(EntityType.BUSINESS, "McDonald's", result)
    entity = _sample_entity(name="McDonald's")
    match = asyncio.run(retrieve_similar_research(entity))
    assert match is None


def test_dissimilar_entity_returns_no_match():
    index_research_result(
        EntityType.BUSINESS,
        "McDonald's",
        _sample_result(),
        context="fast food burgers",
    )
    entity = Entity(
        entity_id="ent-2",
        name="IBM enterprise software",
        entity_type=EntityType.BUSINESS,
        risk_category="business_location",
        context="Enterprise software licensing contract.",
        location=ScriptLocation(page_number=2, scene_number=1, line_excerpt="IBM HQ"),
        confidence=0.9,
        requires_human_review=True,
    )
    match = asyncio.run(retrieve_similar_research(entity))
    assert match is None


def test_build_rag_text_includes_type_and_context():
    entity = _sample_entity(name="Love Story", context="A romantic film title.")
    query = build_rag_query_text(entity)
    assert "entity_type: business" in query
    assert "name: Love Story" in query
    assert "context: A romantic film title." in query

    doc = build_rag_document_text(
        EntityType.BUSINESS,
        "Love Story",
        _sample_result(name="Love Story", finding="1970 romantic drama film."),
        context="film title",
    )
    assert "finding: 1970 romantic drama film." in doc
    assert "citations:" in doc


def test_synthesize_rag_result_adapts_entity_name():
    entity = _sample_entity(name="Golden Arches", entity_id="ent-77")
    source = _sample_result(name="McDonald's")
    adapted = asyncio.run(
        synthesize_rag_result(entity, source, source_name="McDonald's")
    )
    assert adapted.entity_id == "ent-77"
    assert adapted.entity_name == "Golden Arches"
    assert "McDonald's" in (adapted.research_notes or "")


def test_research_metrics_summary():
    metrics = ResearchMetrics()
    metrics.record(ResearchSource.RAG_HIGH)
    metrics.record(ResearchSource.PARALLEL)
    metrics.record(ResearchSource.PERSISTENT_CACHE)
    assert metrics.parallel_calls() == 1
    summary = metrics.summary_lines()[0]
    assert "rag_high=1" in summary
    assert "parallel=1" in summary
