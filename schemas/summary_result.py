"""
schemas/summary_result.py

Structured output produced by the Summary Agent.

Summarises completed RiskResult items for a clearance run. The Summary Agent
does NOT change risk classifications — counts are validated against the
supplied RiskResult list.
"""
from pydantic import BaseModel, Field, model_validator


class SummaryResult(BaseModel):
    """Plain-language overview of a screenplay clearance run for legal review."""

    overall_summary: str = Field(
        ...,
        min_length=1,
        description="Concise plain-language overview of the clearance run",
    )
    total_entities: int = Field(..., ge=0)
    clear_count: int = Field(..., ge=0)
    caution_count: int = Field(..., ge=0)
    high_risk_count: int = Field(..., ge=0)
    priority_items: list[str] = Field(
        default_factory=list,
        description="High-priority items requiring legal attention",
    )

    @model_validator(mode="after")
    def validate_counts(self) -> "SummaryResult":
        expected_total = self.clear_count + self.caution_count + self.high_risk_count
        if self.total_entities != expected_total:
            raise ValueError(
                f"total_entities ({self.total_entities}) must equal "
                f"clear + caution + high_risk ({expected_total})"
            )
        if not self.overall_summary.strip():
            raise ValueError("overall_summary must not be empty")
        return self
