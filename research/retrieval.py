"""
research/retrieval.py

Semantic lookup for prior entity research (tier 2 between exact cache and Parallel).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from research.cache import entity_cache_key, is_cacheable_research
from research.embeddings import embed_text
from research.rag_llm import rerank_vector_hits
from research.rag_config import (
    build_rag_document_text,
    build_rag_query_text,
    research_rag_enabled,
    research_rag_high_score,
    research_rag_medium_score,
    research_rag_top_k,
)
from research.vector_store import VectorSearchHit, get_research_vector_store
from schemas.entities import Entity, EntityType
from schemas.research_result import ResearchResult

logger = logging.getLogger("agentic_cinema.research_rag")


@dataclass(frozen=True)
class RagMatch:
    score: float
    tier: str  # "high" | "medium"
    source_name: str
    source_cache_key: str
    result: ResearchResult
    context_snippet: str | None = None


def rag_high_score_threshold() -> float:
    return research_rag_high_score()


def rag_medium_score_threshold() -> float:
    return research_rag_medium_score()


def index_research_result(
    entity_type: EntityType,
    name: str,
    result: ResearchResult,
    *,
    context: str | None = None,
) -> bool:
    """
    Embed and store research for future semantic retrieval.
    
    Returns:
        True if indexing succeeded, False if it failed.
        
    Raises:
        Exception: Critical errors (dimension mismatches, config issues) are raised
                   to surface them rather than silent failure.
    """
    if not research_rag_enabled() or not is_cacheable_research(result):
        return False
    try:
        document_text = build_rag_document_text(entity_type, name, result, context=context)
        embedding = embed_text(document_text)
        generic = result.model_copy(update={"entity_id": None})
        get_research_vector_store().upsert(
            entity_type,
            name,
            embedding,
            generic,
            context=context,
        )
        logger.info("Successfully indexed research for RAG: %s", name)
        return True
    except (ValueError, RuntimeError) as e:
        # Dimension errors and configuration issues should be raised
        # so they don't get masked as SUCCESS in the pipeline
        error_msg = str(e).lower()
        if "dimension" in error_msg or "2048" in error_msg or "invalid" in error_msg:
            logger.error(
                "RAG indexing failed for %s due to dimension mismatch: %s. "
                "This indicates a configuration issue that must be fixed.",
                name,
                e,
            )
            raise RuntimeError(
                f"Failed to index research for RAG ({name}): {e}. "
                "Check RESEARCH_EMBEDDING_DIMENSIONALITY configuration."
            ) from e
        # Re-raise other ValueError/RuntimeError
        logger.error("RAG indexing failed for %s: %s", name, e)
        raise
    except Exception as e:
        # Transient errors (network, API limits) are logged but don't fail the pipeline
        logger.warning(
            "Failed to index research for RAG (%s): %s. This may be transient.",
            name,
            e,
            exc_info=True,
        )
        return False


async def retrieve_similar_research(entity: Entity) -> RagMatch | None:
    """Return the best semantic match at or above the medium score threshold."""
    if not research_rag_enabled():
        return None
    try:
        query_text = build_rag_query_text(entity)
        query_embedding = await asyncio.to_thread(embed_text, query_text)
        exclude_key = entity_cache_key(entity.entity_type, entity.name)
        hits = await asyncio.to_thread(
            _search_hits,
            entity.entity_type,
            query_embedding,
            exclude_key,
        )
        if not hits:
            return None
        best_hit = await rerank_vector_hits(entity, hits)
        if best_hit is None:
            return None
        best = best_hit
        high = rag_high_score_threshold()
        medium = rag_medium_score_threshold()
        if best.score >= high:
            tier = "high"
        elif best.score >= medium:
            tier = "medium"
        else:
            return None
        return RagMatch(
            score=best.score,
            tier=tier,
            source_name=best.entity_name,
            source_cache_key=best.cache_key,
            result=best.research_result,
            context_snippet=best.context_snippet,
        )
    except Exception:
        logger.warning("RAG retrieval failed for %s", entity.name, exc_info=True)
        return None


def build_rag_prompt_context(match: RagMatch) -> str:
    """Prior evidence block injected into the specialist prompt on medium-tier hits."""
    citations = match.result.citations[:3]
    citation_lines = "\n".join(
        f"- {c.summary} ({c.source_url})" for c in citations
    )
    citation_block = f"\nPrior citations:\n{citation_lines}\n" if citation_lines else ""
    return (
        "Similar entity researched previously "
        f"(semantic similarity {match.score:.2f} to '{match.source_name}'):\n"
        f"Finding: {match.result.finding}\n"
        f"{citation_block}"
        "Use this as starting context, but verify findings for the current entity "
        "and run fresh search if the match is not the same real-world subject.\n\n"
    )


def _search_hits(
    entity_type: EntityType,
    query_embedding: list[float],
    exclude_cache_key: str,
) -> list[VectorSearchHit]:
    return get_research_vector_store().search(
        entity_type,
        query_embedding,
        top_k=research_rag_top_k(),
        exclude_cache_key=exclude_cache_key,
    )
