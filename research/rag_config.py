"""
research/rag_config.py

Environment-driven settings for semantic research retrieval (RAG).
"""
from __future__ import annotations

import os

from schemas.entities import Entity, EntityType
from schemas.research_result import ResearchResult


def research_rag_enabled() -> bool:
    raw = os.getenv("RESEARCH_RAG_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def research_rag_high_score() -> float:
    return _float_env("RESEARCH_RAG_HIGH_SCORE", 0.85)


def research_rag_medium_score() -> float:
    return _float_env("RESEARCH_RAG_MEDIUM_SCORE", 0.72)


def research_rag_top_k() -> int:
    raw = os.getenv("RESEARCH_RAG_TOP_K", "3").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 3
    return max(1, value)


def research_embedding_model() -> str:
    return os.getenv("RESEARCH_EMBEDDING_MODEL", "gemini-embedding-001").strip()


def research_rag_backend() -> str:
    return os.getenv("RESEARCH_RAG_BACKEND", "auto").strip().lower()


def research_embedding_backend() -> str:
    return os.getenv("RESEARCH_EMBEDDING_BACKEND", "gemini").strip().lower()


def research_embedding_dimensionality() -> int:
    """Target embedding dimensionality for Firestore vector storage (max 2048)."""
    raw = os.getenv("RESEARCH_EMBEDDING_DIMENSIONALITY", "1536").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 1536
    # Firestore has a hard limit of 2048 dimensions for native vector search
    return max(1, min(2048, value))


def build_rag_query_text(entity: Entity) -> str:
    """Text embedded when looking up similar past research."""
    context = (entity.context or "").strip()
    parts = [
        f"entity_type: {entity.entity_type.value}",
        f"name: {entity.name}",
    ]
    if context:
        parts.append(f"context: {context[:500]}")
    return "\n".join(parts)


def build_rag_document_text(
    entity_type: EntityType | str,
    name: str,
    result: ResearchResult,
    *,
    context: str | None = None,
) -> str:
    """Text embedded when indexing a successful research result."""
    type_value = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
    citation_bits = [
        c.summary.strip()
        for c in result.citations
        if (c.summary or "").strip()
    ]
    parts = [
        f"entity_type: {type_value}",
        f"name: {name}",
        f"finding: {(result.finding or '').strip()}",
    ]
    if context and context.strip():
        parts.append(f"context: {context.strip()[:500]}")
    if citation_bits:
        parts.append("citations: " + "; ".join(citation_bits[:5]))
    return "\n".join(parts)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    return min(1.0, max(0.0, value))
