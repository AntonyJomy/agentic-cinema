"""
schemas/gatekeeper_result.py

Deterministic governance output from the Gatekeeper.

The Gatekeeper evaluates whether a clearance run may proceed to final
report/export based on risk classifications and human legal-review decisions.
It does NOT perform research or modify upstream results.
"""
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class GatekeeperStatus(str, Enum):
    """Whether a clearance run may proceed to final report/export."""

    BLOCKED = "blocked"
    CLEARED = "cleared"


class GatekeeperReason(str, Enum):
    """Explainable reason code for the gatekeeper decision."""

    NO_BLOCKING_CONDITIONS = "no_blocking_conditions"
    ALL_REQUIRED_REVIEWS_COMPLETE = "all_required_reviews_complete"
    HIGH_RISK_UNRESOLVED = "high_risk_unresolved"
    HUMAN_REVIEW_PENDING = "human_review_pending"
    HUMAN_REVIEW_BLOCKED = "human_review_blocked"
    RUN_BLOCKED = "run_blocked"


class GatekeeperResult(BaseModel):
    """Auditable gatekeeper decision for one clearance run."""

    status: GatekeeperStatus
    reason: GatekeeperReason
    message: str = Field(..., min_length=1)
    blocking_entity_ids: list[str] = Field(default_factory=list)

    @property
    def cleared_for_export(self) -> bool:
        return self.status == GatekeeperStatus.CLEARED

    @model_validator(mode="after")
    def validate_consistency(self) -> "GatekeeperResult":
        if self.status == GatekeeperStatus.BLOCKED and not self.message.strip():
            raise ValueError("blocked gatekeeper results must include a message")
        if self.status == GatekeeperStatus.CLEARED and self.blocking_entity_ids:
            raise ValueError("cleared gatekeeper results must not include blocking_entity_ids")
        if self.status == GatekeeperStatus.BLOCKED and not self.blocking_entity_ids:
            if self.reason not in {GatekeeperReason.RUN_BLOCKED}:
                raise ValueError("blocked gatekeeper results must identify blocking entities")
        return self
