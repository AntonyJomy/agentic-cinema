"""
gatekeeper/clearance_gate.py

Deterministic Gatekeeper for screenplay E&O clearance runs.

Evaluates whether a clearance run may proceed to final report/export based
on existing risk classifications and human legal-review decisions.

This is NOT an LLM agent. It does NOT perform research, call Parallel, change
risk classifications, or override human decisions.
"""
from __future__ import annotations

from schemas.gatekeeper_result import (
    GatekeeperReason,
    GatekeeperResult,
    GatekeeperStatus,
)
from schemas.legal_review import LegalReviewPackage, ReviewDecision
from schemas.risk_result import RiskLevel


def _blocking_records(package: LegalReviewPackage) -> list:
    """Return entity review records that block clearance."""
    blocking = []
    for record in package.entity_reviews:
        if not record.requires_explicit_decision:
            continue
        if record.decision == ReviewDecision.APPROVED and record.reviewer:
            continue
        blocking.append(record)
    return blocking


def _build_block_message(blocking_records: list) -> str:
    names = [record.entity_name for record in blocking_records]
    high_risk_pending = [
        record
        for record in blocking_records
        if record.ai_risk_level == RiskLevel.HIGH_RISK
        and record.decision == ReviewDecision.NEEDS_REVIEW
    ]
    explicitly_blocked = [
        record for record in blocking_records if record.decision == ReviewDecision.BLOCKED
    ]

    if high_risk_pending and explicitly_blocked:
        return (
            f"{len(blocking_records)} findings block clearance: "
            f"{len(high_risk_pending)} high-risk item(s) lack legal approval and "
            f"{len(explicitly_blocked)} item(s) were blocked by the reviewer "
            f"({', '.join(names)})."
        )
    if high_risk_pending:
        count = len(high_risk_pending)
        noun = "finding has" if count == 1 else "findings have"
        return (
            f"{count} high-risk {noun} not received legal approval "
            f"({', '.join(record.entity_name for record in high_risk_pending)})."
        )
    if explicitly_blocked:
        count = len(explicitly_blocked)
        noun = "finding was" if count == 1 else "findings were"
        return (
            f"{count} {noun} explicitly blocked by the legal reviewer "
            f"({', '.join(record.entity_name for record in explicitly_blocked)})."
        )

    count = len(blocking_records)
    noun = "item requires" if count == 1 else "items require"
    return (
        f"{count} {noun} explicit legal review before clearance "
        f"({', '.join(names)})."
    )


def _determine_block_reason(blocking_records: list) -> GatekeeperReason:
    if any(record.decision == ReviewDecision.BLOCKED for record in blocking_records):
        return GatekeeperReason.HUMAN_REVIEW_BLOCKED
    if any(
        record.ai_risk_level == RiskLevel.HIGH_RISK
        and record.decision == ReviewDecision.NEEDS_REVIEW
        for record in blocking_records
    ):
        return GatekeeperReason.HIGH_RISK_UNRESOLVED
    return GatekeeperReason.HUMAN_REVIEW_PENDING


def evaluate_clearance(package: LegalReviewPackage) -> GatekeeperResult:
    """
    Evaluate whether a clearance run may proceed to final report/export.

    Rules:
    - Required high-risk / human-review entities must be explicitly APPROVED
    - NEEDS_REVIEW or BLOCKED decisions block clearance
    - Run-level BLOCKED decision blocks clearance
    """
    if package.overall_decision == ReviewDecision.BLOCKED:
        blocking_records = _blocking_records(package)
        blocking_ids = [record.entity_id for record in blocking_records]
        if not blocking_ids:
            return GatekeeperResult(
                status=GatekeeperStatus.BLOCKED,
                reason=GatekeeperReason.RUN_BLOCKED,
                message="The legal reviewer blocked this clearance run.",
                blocking_entity_ids=["__run__"],
            )
        return GatekeeperResult(
            status=GatekeeperStatus.BLOCKED,
            reason=GatekeeperReason.RUN_BLOCKED,
            message="The legal reviewer blocked this clearance run.",
            blocking_entity_ids=blocking_ids,
        )

    blocking_records = _blocking_records(package)
    if blocking_records:
        return GatekeeperResult(
            status=GatekeeperStatus.BLOCKED,
            reason=_determine_block_reason(blocking_records),
            message=_build_block_message(blocking_records),
            blocking_entity_ids=[record.entity_id for record in blocking_records],
        )

    required_reviews = [
        record for record in package.entity_reviews if record.requires_explicit_decision
    ]
    if required_reviews:
        return GatekeeperResult(
            status=GatekeeperStatus.CLEARED,
            reason=GatekeeperReason.ALL_REQUIRED_REVIEWS_COMPLETE,
            message=(
                "All required high-risk findings have been explicitly approved "
                "by the legal reviewer."
            ),
            blocking_entity_ids=[],
        )

    return GatekeeperResult(
        status=GatekeeperStatus.CLEARED,
        reason=GatekeeperReason.NO_BLOCKING_CONDITIONS,
        message="No high-risk findings require legal review. Cleared for report.",
        blocking_entity_ids=[],
    )
