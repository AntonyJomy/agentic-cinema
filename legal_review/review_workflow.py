"""
legal_review/review_workflow.py

Legal Review workflow for screenplay E&O clearance.

Presents AI-generated findings to a human legal reviewer and records explicit
human decisions with a full audit trail.

This is NOT an LLM agent and does NOT make legal decisions. The AI cannot
approve its own high-risk findings — all decisions require explicit human input.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from schemas.legal_review import (
    EntityReviewRecord,
    LegalReviewPackage,
    ReviewDecision,
)
from schemas.risk_result import RiskLevel
from schemas.summary_result import SummaryResult

if TYPE_CHECKING:
    from orchestrator import EntityResult


def requires_explicit_decision(record: EntityReviewRecord) -> bool:
    """Return True if this entity must receive an explicit human decision."""
    return record.requires_explicit_decision


def build_entity_review_record(result: EntityResult) -> EntityReviewRecord:
    """Build an unresolved review record from a scored entity result."""
    risk = result.risk_result
    research = result.research_result
    entity = result.entity

    if risk is None:
        return EntityReviewRecord(
            entity_id=entity.entity_id,
            entity_name=entity.name,
            entity_type=entity.entity_type,
            context=entity.context,
            ai_risk_level=RiskLevel.CAUTION,
            ai_triggered_rule="research_unavailable",
            ai_reasoning="Specialist research was not available for scoring.",
            ai_research_confidence=0.0,
            ai_finding=research.finding if research else None,
            evidence=list(research.citations) if research else [],
            requires_human_review=entity.requires_human_review,
            decision=ReviewDecision.NEEDS_REVIEW,
        )

    return EntityReviewRecord(
        entity_id=entity.entity_id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        context=entity.context,
        ai_risk_level=risk.risk_level,
        ai_triggered_rule=risk.triggered_rule,
        ai_reasoning=risk.reasoning,
        ai_research_confidence=risk.research_confidence,
        ai_finding=research.finding if research else None,
        evidence=list(risk.evidence),
        requires_human_review=risk.requires_human_review,
        decision=ReviewDecision.NEEDS_REVIEW,
    )


def build_legal_review_package(
    entity_results: dict,
    *,
    run_id: str,
    script_id: str,
    script_title: str | None = None,
    summary_result: SummaryResult | None = None,
) -> LegalReviewPackage:
    """
    Assemble the clearance run package for human legal review.

    All entities default to NEEDS_REVIEW — no approvals are inferred.
    """
    entity_reviews: list[EntityReviewRecord] = []
    for results_list in entity_results.values():
        for result in results_list:
            entity_reviews.append(build_entity_review_record(result))

    return LegalReviewPackage(
        run_id=run_id,
        script_id=script_id,
        script_title=script_title,
        summary=summary_result,
        entity_reviews=entity_reviews,
        overall_decision=ReviewDecision.NEEDS_REVIEW,
    )


def record_entity_decision(
    package: LegalReviewPackage,
    entity_id: str,
    decision: ReviewDecision,
    reviewer: str,
    comment: str | None = None,
) -> LegalReviewPackage:
    """
    Record an explicit human decision for one entity.

    Preserves the original AI risk classification. Returns a new package
    with the updated audit record.
    """
    if not reviewer.strip():
        raise ValueError("reviewer identifier is required for auditable decisions")

    updated_reviews: list[EntityReviewRecord] = []
    found = False
    for record in package.entity_reviews:
        if record.entity_id != entity_id:
            updated_reviews.append(record)
            continue

        found = True
        updated_reviews.append(
            record.model_copy(
                update={
                    "decision": decision,
                    "reviewer": reviewer,
                    "reviewed_at": datetime.now(timezone.utc),
                    "comment": comment,
                }
            )
        )

    if not found:
        raise ValueError(f"Entity {entity_id} not found in review package")

    return package.model_copy(update={"entity_reviews": updated_reviews})


def record_overall_decision(
    package: LegalReviewPackage,
    decision: ReviewDecision,
    reviewer: str,
    comment: str | None = None,
) -> LegalReviewPackage:
    """
    Record an explicit run-level human decision.

    Raises if required entity-level reviews are still unresolved.
    """
    if not reviewer.strip():
        raise ValueError("reviewer identifier is required for auditable decisions")

    if decision == ReviewDecision.APPROVED and not all_required_reviews_resolved(package):
        raise ValueError(
            "Cannot approve run: high-risk entities still require explicit human decisions"
        )

    return package.model_copy(
        update={
            "overall_decision": decision,
            "reviewed_by": reviewer,
            "reviewed_at": datetime.now(timezone.utc),
        }
    )


def all_required_reviews_resolved(package: LegalReviewPackage) -> bool:
    """Return True when every entity requiring explicit review has a human decision."""
    return package.unresolved_required_count == 0


def get_pending_required_reviews(package: LegalReviewPackage) -> list[EntityReviewRecord]:
    """Return entities that still require an explicit human decision."""
    return [
        record
        for record in package.entity_reviews
        if record.requires_explicit_decision and not record.is_resolved
    ]


def to_firestore_entity_status(decision: ReviewDecision) -> str | None:
    """Map a human review decision to Firestore entity status conventions."""
    from schemas.legal_review import DECISION_TO_FIRESTORE_STATUS

    return DECISION_TO_FIRESTORE_STATUS.get(decision)
