"""
schemas/risk_result.py

Structured output produced by the Risk Scoring Agent.

This is DISTINCT from:
- Entity.confidence (extraction confidence)
- ResearchResult.confidence (research/evidence confidence)

RiskResult.risk_level is the clearance rubric outcome (clear / caution / high_risk).
"""
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from schemas.entities import EntityType
from schemas.research_result import Citation


class RiskLevel(str, Enum):
    """Clearance rubric outcome for one grounded, researched entity."""

    CLEAR = "clear"
    CAUTION = "caution"
    HIGH_RISK = "high_risk"


class RiskResult(BaseModel):
    """Risk scoring output for one Entity + specialist ResearchResult pair."""

    entity_id: str = Field(..., min_length=1)
    entity_name: str = Field(..., min_length=1)
    entity_type: EntityType
    risk_level: RiskLevel = Field(
        ...,
        description=(
            "Clearance rubric outcome: clear, caution, or high_risk. "
            "This is NOT research confidence."
        ),
    )
    triggered_rule: str = Field(
        ...,
        min_length=1,
        description="The rubric rule that determined this risk level",
    )
    reasoning: str = Field(
        ...,
        min_length=1,
        description="Explanation of why this entity received this risk level",
    )
    evidence: list[Citation] = Field(
        default_factory=list,
        description="Supporting evidence drawn from the specialist citations",
    )
    research_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Research confidence from the specialist finding — informational only, "
            "NOT the risk score."
        ),
    )
    requires_human_review: bool = Field(
        default=False,
        description="Whether this entity requires human/legal review",
    )

    @model_validator(mode="after")
    def validate_identity_consistency(self) -> "RiskResult":
        if not self.reasoning.strip():
            raise ValueError("reasoning must not be empty")
        if not self.triggered_rule.strip():
            raise ValueError("triggered_rule must not be empty")
        return self
