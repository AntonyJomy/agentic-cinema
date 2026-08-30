"""
research/rag_llm.py

LLM reranking and synthesis for semantic research retrieval.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from agents.model_config import get_gemini_model
from research.vector_store import VectorSearchHit
from schemas.entities import Entity
from schemas.research_result import ResearchResult, ResearchStatus

logger = logging.getLogger("agentic_cinema.research_rag")


def research_rag_rerank_enabled() -> bool:
    raw = os.getenv("RESEARCH_RAG_RERANK_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def research_rag_synthesis_enabled() -> bool:
    raw = os.getenv("RESEARCH_RAG_SYNTHESIS_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def research_rag_llm_backend() -> str:
    return os.getenv("RESEARCH_RAG_LLM_BACKEND", "gemini").strip().lower()


def _gemini_client():
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY required for RAG LLM")
    return genai.Client(api_key=api_key)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


async def rerank_vector_hits(
    entity: Entity,
    hits: list[VectorSearchHit],
) -> VectorSearchHit | None:
    """Pick the best semantic match from vector candidates, or reject all."""
    if not hits:
        return None
    if not research_rag_rerank_enabled() or len(hits) == 1:
        return hits[0]

    backend = research_rag_llm_backend()
    if backend == "test":
        return hits[0]

    candidates = []
    for index, hit in enumerate(hits):
        candidates.append(
            {
                "index": index,
                "source_name": hit.entity_name,
                "vector_score": round(hit.score, 4),
                "finding": hit.research_result.finding[:400],
                "context_snippet": (hit.context_snippet or "")[:200],
            }
        )
    prompt = (
        "You are disambiguating screenplay clearance research.\n"
        f"Query entity type: {entity.entity_type.value}\n"
        f"Query name: {entity.name}\n"
        f"Query context: {(entity.context or '')[:400]}\n\n"
        "Candidates from vector search:\n"
        f"{json.dumps(candidates, indent=2)}\n\n"
        "Return JSON only: "
        '{"best_index": <int or null>, "same_subject": <true|false>} '
        "Use null when no candidate refers to the same real-world subject."
    )
    try:
        client = _gemini_client()
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
        )
        payload = _extract_json_object(getattr(response, "text", "") or "")
        if not payload.get("same_subject"):
            return None
        best_index = payload.get("best_index")
        if best_index is None:
            return None
        if not isinstance(best_index, int) or best_index < 0 or best_index >= len(hits):
            return None
        return hits[best_index]
    except Exception:
        logger.warning("RAG rerank failed for %s; using top vector hit", entity.name, exc_info=True)
        return hits[0]


async def synthesize_rag_result(entity: Entity, source: ResearchResult, *, source_name: str) -> ResearchResult:
    """Adapt prior research to the current entity instead of copy-pasting."""
    if not research_rag_synthesis_enabled():
        return source.model_copy(
            update={
                "entity_id": entity.entity_id,
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
            }
        )

    backend = research_rag_llm_backend()
    if backend == "test":
        note = f"Adapted from prior research on '{source_name}'."
        existing = (source.research_notes or "").strip()
        notes = f"{note} {existing}".strip()
        return source.model_copy(
            update={
                "entity_id": entity.entity_id,
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "research_notes": notes,
            }
        )

    prompt = (
        "Adapt prior clearance research for a new screenplay entity.\n"
        "Keep citations when still relevant. Do not invent new sources.\n"
        f"Prior entity name: {source_name}\n"
        f"New entity JSON:\n{entity.model_dump_json(indent=2)}\n\n"
        f"Prior research JSON:\n{source.model_dump_json(indent=2)}\n\n"
        "Return a single JSON object matching the ResearchResult schema for the NEW entity. "
        "Set status to success when adapted confidently; insufficient_evidence if ambiguous."
    )
    try:
        client = _gemini_client()
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
        )
        payload = _extract_json_object(getattr(response, "text", "") or "")
        payload["entity_id"] = entity.entity_id
        payload["entity_name"] = entity.name
        payload["entity_type"] = entity.entity_type.value
        return ResearchResult.model_validate(payload)
    except Exception:
        logger.warning(
            "RAG synthesis failed for %s; falling back to adapted copy",
            entity.name,
            exc_info=True,
        )
        return source.model_copy(
            update={
                "entity_id": entity.entity_id,
                "entity_name": entity.name,
                "entity_type": entity.entity_type,
                "research_notes": f"Adapted from prior research on '{source_name}' (synthesis fallback).",
                "status": ResearchStatus.SUCCESS,
            }
        )
