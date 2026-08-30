"""
api/schemas.py

HTTP request/response models for the clearance API.
"""
from pydantic import BaseModel, Field

from schemas.legal_review import ReviewDecision


class ClearanceRequest(BaseModel):
    """POST /clearance request body.

    Identity fields (user_id, reviewer_id, reviewer_name, role) are rejected
    by omission — the server uses get_current_user() only.
    """

    script: str = Field(..., min_length=1, description="Screenplay text")
    script_title: str | None = Field(None, description="Optional script title")
    source_file_name: str | None = Field(
        None, description="Original filename for display only"
    )
    run_id: str | None = Field(
        None,
        description="Stable run_id returned by /extract-script. "
        "When provided the pipeline and Firestore record use this exact id.",
    )
    script_file_url: str | None = Field(
        None,
        description="gs:// URL returned by /extract-script. "
        "Stored as script_file_url on the Firestore run document.",
    )


class ExtractScriptResponse(BaseModel):
    """POST /extract-script response body."""

    run_id: str = Field(..., description="Stable run ID to pass to /clearance")
    script: str = Field(..., description="Extracted screenplay text")
    filename: str = Field(..., description="Original uploaded filename")
    page_count: int | None = Field(
        None, description="PDF page count when source was a PDF"
    )
    script_title: str | None = Field(None, description="Optional script title")
    script_file_url: str | None = Field(
        None, description="gs:// URL of the uploaded file in Cloud Storage"
    )


class EntityDecisionRequest(BaseModel):
    """POST /clearance/{run_id}/entities/{entity_id}/decision"""

    decision: ReviewDecision
    comment: str | None = Field(None, max_length=2000)


class OverallDecisionRequest(BaseModel):
    """POST /clearance/{run_id}/decision

    The server records this request then re-runs evaluate_clearance().
    Sending APPROVED does not force cleared_for_export.
    """

    decision: ReviewDecision
    comment: str | None = Field(None, max_length=2000)


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
    script_file_url: str | None = None  # Cloud Storage URL for uploaded file
    report_file_url: str | None = None  # Cloud Storage URL for the clearance report PDF
    report_hash: str | None = None      # SHA-256 hex digest of the report PDF
    created_at: str
    updated_at: str
    overall_status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    entities: list[ClearanceEntityResponse]
    metadata: dict = Field(default_factory=dict)


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
