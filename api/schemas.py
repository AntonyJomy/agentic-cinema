"""
api/schemas.py

HTTP request/response models for the clearance API.
"""
from pydantic import BaseModel, Field


class ClearanceRequest(BaseModel):
    """POST /clearance request body."""

    script: str = Field(..., min_length=1, description="Screenplay text")
    script_title: str | None = Field(None, description="Optional script title")


class ClearanceEntityResponse(BaseModel):
    """Entity shape compatible with the frontend run document."""

    entity_id: str
    name: str
    entity_type: str
    risk_category: str
    context: str
    location: dict
    confidence: float
    requires_human_review: bool
    extraction_notes: str | None = None
    evidence: list[dict] = Field(default_factory=list)
    status: str
    risk_level: str | None = None
    research_finding: str | None = None
    research_confidence: float | None = None
    ai_reasoning: str | None = None
    triggered_rule: str | None = None
    legal_decision: str | None = None


class ClearanceRunResponse(BaseModel):
    """Frontend-compatible clearance run document."""

    run_id: str
    script_id: str
    script_title: str | None = None
    created_at: str
    updated_at: str
    overall_status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    entities: list[ClearanceEntityResponse]
    metadata: dict


class ClearanceResponse(BaseModel):
    """Structured clearance pipeline result for the frontend."""

    run: ClearanceRunResponse
    summary: dict | None = None
    legal_review: dict | None = None
    gatekeeper: dict | None = None
    statistics: dict | None = None
    recommendations: list[str] = Field(default_factory=list)
    cleared_for_export: bool = False
    duration_seconds: float = 0.0
