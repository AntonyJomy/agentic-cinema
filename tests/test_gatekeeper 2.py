"""
tests/test_gatekeeper.py

Tests the deterministic Gatekeeper clearance gate.
No Parallel MCP or LLM calls are made.
"""
from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from datetime import datetime, timezone

from gatekeeper.clearance_gate import evaluate_clearance
from legal_review.review_workflow import record_entity_decision
from schemas.entities import EntityType
from schemas.gatekeeper_result import GatekeeperReason, GatekeeperStatus
from schemas.legal_review import EntityReviewRecord, LegalReviewPackage, ReviewDecision
from schemas.risk_result import RiskLevel

REVIEWER = "Ben Okafor (Legal)"


def make_review_record(
    entity_id: str,
    name: str,
    *,
    risk_level: RiskLevel,
    decision: ReviewDecision = ReviewDecision.NEEDS_REVIEW,
    requires_human_review: bool = False,
    reviewer: str | None = None,
) -> EntityReviewRecord:
    return EntityReviewRecord(
        entity_id=entity_id,
        entity_name=name,
        entity_type=EntityType.BUSINESS,
        context=f"Context for {name}.",
        ai_risk_level=risk_level,
        ai_triggered_rule=f"{risk_level.value}_rule",
        ai_reasoning=f"AI reasoning for {name}.",
        ai_research_confidence=0.9,
        requires_human_review=requires_human_review,
        decision=decision,
        reviewer=reviewer,
        reviewed_at=datetime.now(timezone.utc) if reviewer else None,
    )


def make_package(*records: EntityReviewRecord) -> LegalReviewPackage:
    return LegalReviewPackage(
        run_id="run-gate-test",
        script_id="script-gate-test",
        script_title="Gatekeeper Test",
        entity_reviews=list(records),
    )


def test_no_high_risk_cleared() -> bool:
    package = make_package(
        make_review_record("e1", "Zorbax Industries", risk_level=RiskLevel.CLEAR),
        make_review_record("e2", "Sunny's Workshop", risk_level=RiskLevel.CAUTION),
    )
    result = evaluate_clearance(package)

    if result.status != GatekeeperStatus.CLEARED:
        print(f"FAILED: expected CLEARED, got {result.status}")
        return False
    if not result.cleared_for_export:
        print("FAILED: expected cleared_for_export=True")
        return False
    if result.blocking_entity_ids:
        print("FAILED: expected no blocking entity IDs")
        return False

    print("PASSED: no high-risk findings → CLEARED")
    return True


def test_high_risk_no_legal_review_blocked() -> bool:
    package = make_package(
        make_review_record("e-high", "McDonald's", risk_level=RiskLevel.HIGH_RISK),
    )
    result = evaluate_clearance(package)

    if result.status != GatekeeperStatus.BLOCKED:
        print(f"FAILED: expected BLOCKED, got {result.status}")
        return False
    if "e-high" not in result.blocking_entity_ids:
        print("FAILED: high-risk entity should be in blocking_entity_ids")
        return False
    if result.reason not in {
        GatekeeperReason.HIGH_RISK_UNRESOLVED,
        GatekeeperReason.HUMAN_REVIEW_PENDING,
    }:
        print(f"FAILED: unexpected reason {result.reason}")
        return False

    print("PASSED: high-risk with no legal review → BLOCKED")
    return True


def test_high_risk_needs_review_blocked() -> bool:
    package = make_package(
        make_review_record(
            "e-high",
            "McDonald's",
            risk_level=RiskLevel.HIGH_RISK,
            decision=ReviewDecision.NEEDS_REVIEW,
        ),
    )
    result = evaluate_clearance(package)

    if result.status != GatekeeperStatus.BLOCKED:
        print(f"FAILED: expected BLOCKED, got {result.status}")
        return False
    if result.reason != GatekeeperReason.HIGH_RISK_UNRESOLVED:
        print(f"FAILED: expected HIGH_RISK_UNRESOLVED, got {result.reason}")
        return False

    print("PASSED: high-risk + NEEDS_REVIEW → BLOCKED")
    return True


def test_high_risk_approved_cleared() -> bool:
    package = make_package(
        make_review_record(
            "e-high",
            "McDonald's",
            risk_level=RiskLevel.HIGH_RISK,
            decision=ReviewDecision.APPROVED,
            reviewer=REVIEWER,
        ),
    )
    result = evaluate_clearance(package)

    if result.status != GatekeeperStatus.CLEARED:
        print(f"FAILED: expected CLEARED, got {result.status}")
        return False
    if result.reason != GatekeeperReason.ALL_REQUIRED_REVIEWS_COMPLETE:
        print(f"FAILED: expected ALL_REQUIRED_REVIEWS_COMPLETE, got {result.reason}")
        return False
    if not result.cleared_for_export:
        print("FAILED: expected cleared_for_export=True")
        return False

    print("PASSED: high-risk + explicit APPROVED → CLEARED")
    return True


def test_high_risk_blocked_decision() -> bool:
    package = make_package(
        make_review_record(
            "e-high",
            "McDonald's",
            risk_level=RiskLevel.HIGH_RISK,
            decision=ReviewDecision.BLOCKED,
            reviewer=REVIEWER,
        ),
    )
    result = evaluate_clearance(package)

    if result.status != GatekeeperStatus.BLOCKED:
        print(f"FAILED: expected BLOCKED, got {result.status}")
        return False
    if result.reason != GatekeeperReason.HUMAN_REVIEW_BLOCKED:
        print(f"FAILED: expected HUMAN_REVIEW_BLOCKED, got {result.reason}")
        return False
    if "e-high" not in result.blocking_entity_ids:
        print("FAILED: blocked entity should appear in blocking_entity_ids")
        return False

    print("PASSED: high-risk + BLOCKED → BLOCKED")
    return True


def test_ai_classification_preserved() -> bool:
    package = make_package(
        make_review_record(
            "e-high",
            "McDonald's",
            risk_level=RiskLevel.HIGH_RISK,
            decision=ReviewDecision.APPROVED,
            reviewer=REVIEWER,
        ),
    )
    original_ai = package.entity_reviews[0].ai_risk_level
    result = evaluate_clearance(package)

    if package.entity_reviews[0].ai_risk_level != original_ai:
        print("FAILED: gatekeeper modified AI risk classification")
        return False
    if result.status != GatekeeperStatus.CLEARED:
        print("FAILED: expected clearance after approval")
        return False

    print("PASSED: gatekeeper does not change AI classifications")
    return True


def test_recorded_decision_flow() -> bool:
    package = make_package(
        make_review_record("e-high", "McDonald's", risk_level=RiskLevel.HIGH_RISK),
    )

    blocked = evaluate_clearance(package)
    if blocked.status != GatekeeperStatus.BLOCKED:
        print("FAILED: should block before human approval")
        return False

    approved_package = record_entity_decision(
        package,
        entity_id="e-high",
        decision=ReviewDecision.APPROVED,
        reviewer=REVIEWER,
        comment="Approved after review.",
    )
    cleared = evaluate_clearance(approved_package)
    if cleared.status != GatekeeperStatus.CLEARED:
        print("FAILED: should clear after explicit human approval")
        return False

    print("PASSED: gatekeeper respects recorded human approval flow")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Gatekeeper")
    print("=" * 60 + "\n")

    tests = [
        test_no_high_risk_cleared,
        test_high_risk_no_legal_review_blocked,
        test_high_risk_needs_review_blocked,
        test_high_risk_approved_cleared,
        test_high_risk_blocked_decision,
        test_ai_classification_preserved,
        test_recorded_decision_flow,
    ]

    results = [test() for test in tests]

    print("\n" + "=" * 60)
    if all(results):
        print("ALL TESTS PASSED")
        sys.exit(0)

    print("TESTS FAILED")
    sys.exit(1)
