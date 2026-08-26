"""
schemas/legal_review.py

Human legal review records for screenplay E&O clearance runs.

The Legal Review workflow presents AI findings to a human reviewer and records
explicit decisions. AI risk classifications are preserved separately and are
never overwritten by human decisions.
"""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from schemas.entities import EntityType
from schemas.research_result import Citation
from schemas.risk_result import RiskLevel
from schemas.summary_result import SummaryResult


class ReviewDecision(str, Enum):
    """Explicit human legal review decision for one entity or run."""

    APPROVED = "approved"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"


# Maps human decisions to Firestore entity status conventions (frontend/Firestore).
DECISION_TO_FIRESTORE_STATUS: dict[ReviewDecision, str | None] = {
    ReviewDecision.APPROVED: "cleared",
    ReviewDecision.BLOCKED: "blocked",
    ReviewDecision.NEEDS_REVIEW: "flagged",
}


class EntityReviewRecord(BaseModel):
    """Auditable human review record for one scored entity."""

    entity_id: str = Field(..., min_length=1)
    entity_name: str = Field(..., min_length=1)
    entity_type: EntityType
    context: str = Field(..., min_length=1)

    ai_risk_level: RiskLevel = Field(
        ...,
        description="Original AI risk classification — never modified by human review",
    )
    ai_triggered_rule: str = Field(..., min_length=1)
    ai_reasoning: str = Field(..., min_length=1)
    ai_research_confidence: float = Field(..., ge=0.0, le=1.0)
    ai_finding: str | None = Field(
        None,
        description="Specialist research finding supplied to the scoring agent",
    )
    evidence: list[Citation] = Field(default_factory=list)

    requires_human_review: bool = Field(default=False)
    decision: ReviewDecision = Field(
        default=ReviewDecision.NEEDS_REVIEW,
        description="Human legal decision — defaults unresolved; never auto-inferred",
    )
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    comment: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.decision != ReviewDecision.NEEDS_REVIEW

    @property
    def requires_explicit_decision(self) -> bool:
        return (
            self.ai_risk_level == RiskLevel.HIGH_RISK
            or self.requires_human_review
        )


class LegalReviewPackage(BaseModel):
    """Complete clearance run package presented for human legal review."""

    run_id: str = Field(..., min_length=1)
    script_id: str = Field(..., min_length=1)
    script_title: str | None = None
    summary: SummaryResult | None = None
    entity_reviews: list[EntityReviewRecord] = Field(default_factory=list)

    overall_decision: ReviewDecision = Field(
        default=ReviewDecision.NEEDS_REVIEW,
        description="Run-level human decision — never auto-inferred from AI scores",
    )
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    @property
    def pending_review_count(self) -> int:
        return sum(1 for record in self.entity_reviews if not record.is_resolved)

    @property
    def unresolved_required_count(self) -> int:
        return sum(
            1
            for record in self.entity_reviews
            if record.requires_explicit_decision and not record.is_resolved
        )

    @model_validator(mode="after")
    def validate_no_auto_approval(self) -> "LegalReviewPackage":
        """Ensure high-risk entities have not been silently approved."""
        for record in self.entity_reviews:
            if (
                record.ai_risk_level == RiskLevel.HIGH_RISK
                and record.decision == ReviewDecision.APPROVED
                and record.reviewer is None
            ):
                raise ValueError(
                    f"Entity {record.entity_id}: high-risk items cannot be "
                    "auto-approved without an explicit reviewer"
                )
        return self
