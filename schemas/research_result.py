"""
schemas/research_result.py

Structured output produced by research specialist agents.

This is DISTINCT from Entity.confidence (extraction confidence).
ResearchResult.confidence is confidence in the RESEARCH FINDING only —
it is NOT a legal risk score (clear / caution / high-risk belong to the
downstream scoring agent).
"""
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from schemas.entities import EntityType


class ResearchStatus(str, Enum):
    """Outcome of the research attempt (not a clearance decision)."""

    SUCCESS = "success"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TOOL_FAILURE = "tool_failure"


class Citation(BaseModel):
    """One web evidence item retrieved via Parallel Search MCP."""

    source_url: str = Field(..., min_length=1, description="URL of the source")
    summary: str = Field(
        ...,
        min_length=1,
        description="Brief summary of what this source contributes",
    )
    retrieved_via: str = Field(
        default="parallel",
        description="How this evidence was obtained (always 'parallel' for MCP search)",
    )

    @field_validator("source_url")
    @classmethod
    def http_https_only(cls, value: str) -> str:
        from urllib.parse import urlparse

        text = (value or "").strip()
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an http or https URL")
        return text


class ResearchResult(BaseModel):
    """Minimum research finding returned by a specialist for one Entity."""

    entity_id: str | None = Field(
        None, description="entity_id from the input Entity, when available"
    )
    entity_name: str = Field(..., min_length=1)
    entity_type: EntityType
    finding: str = Field(
        ...,
        min_length=1,
        description="Concise research finding supported by citations (or failure note)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the research finding based on available evidence. "
            "NOT a legal risk score."
        ),
    )
    citations: list[Citation] = Field(default_factory=list)
    status: ResearchStatus = Field(
        default=ResearchStatus.SUCCESS,
        description="Whether research succeeded, found insufficient evidence, or tools failed",
    )
    research_notes: str | None = Field(
        None,
        description="Optional notes about search strategy, ambiguity, or re-check outcome",
    )
