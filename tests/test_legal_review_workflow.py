"""
tests/test_legal_review_workflow.py

Tests the Legal Review workflow with mocked scored entity results.
No Parallel MCP or LLM calls are made.
"""
from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from legal_review.review_workflow import (  # noqa: E402
    all_required_reviews_resolved,
    build_entity_review_record,
    build_legal_review_package,
    get_pending_required_reviews,
    record_entity_decision,
    record_overall_decision,
)
from orchestrator import EntityResult, SPECIALISTS  # noqa: E402
from schemas.entities import Entity, EntityType, ScriptLocation  # noqa: E402
from schemas.legal_review import ReviewDecision  # noqa: E402
from schemas.research_result import Citation, ResearchResult, ResearchStatus  # noqa: E402
from schemas.risk_result import RiskLevel, RiskResult  # noqa: E402

REVIEWER = "Ben Okafor (Legal)"


def make_entity_result(
    entity_id: str,
    name: str,
    entity_type: EntityType,
    risk_level: RiskLevel,
    requires_human_review: bool = False,
) -> EntityResult:
    entity = Entity(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        context=f"Screenplay context for {name}.",
        location=ScriptLocation(
            scene_number=1,
            line_excerpt=f"Reference to {name}.",
        ),
        confidence=0.9,
        requires_human_review=requires_human_review,
    )
    research = ResearchResult(
        entity_id=entity_id,
        entity_name=name,
        entity_type=entity_type,
        finding=f"Research finding for {name}.",
        confidence=0.85,
        citations=[
            Citation(
                source_url="https://example.com/source",
                summary=f"Evidence for {name}.",
            )
        ],
        status=ResearchStatus.SUCCESS,
    )
    risk = RiskResult(
        entity_id=entity_id,
        entity_name=name,
        entity_type=entity_type,
        risk_level=risk_level,
        triggered_rule=f"{risk_level.value}_rule",
        reasoning=f"AI reasoning for {name} at {risk_level.value}.",
        evidence=list(research.citations),
        research_confidence=research.confidence,
        requires_human_review=requires_human_review,
    )
    return EntityResult(
        entity=entity,
        research_result=research,
        specialist_config=SPECIALISTS[0],
        processing_time=0.0,
        success=True,
        risk_result=risk,
    )


def build_mock_entity_results() -> dict[EntityType, list[EntityResult]]:
    return {
        EntityType.BUSINESS: [
            make_entity_result("e-clear", "Zorbax Industries", EntityType.BUSINESS, RiskLevel.CLEAR),
            make_entity_result(
                "e-high",
                "McDonald's",
                EntityType.BUSINESS,
                RiskLevel.HIGH_RISK,
                requires_human_review=True,
            ),
        ],
        EntityType.SONG: [
            make_entity_result("e-caution", "Love Story", EntityType.SONG, RiskLevel.CAUTION),
        ],
    }


def test_high_risk_requires_human_review() -> bool:
    package = build_legal_review_package(
        build_mock_entity_results(),
        run_id="run-legal-test",
        script_id="script-legal-test",
        script_title="Legal Review Test",
    )

    high_risk_records = [
        record for record in package.entity_reviews if record.ai_risk_level == RiskLevel.HIGH_RISK
    ]
    if len(high_risk_records) != 1:
        print(f"FAILED: expected 1 high-risk record, got {len(high_risk_records)}")
        return False

    record = high_risk_records[0]
    if not record.requires_explicit_decision:
        print("FAILED: high-risk entity should require explicit decision")
        return False
    if record.decision != ReviewDecision.NEEDS_REVIEW:
        print("FAILED: high-risk entity should default to NEEDS_REVIEW")
        return False

    print("PASSED: high-risk item requires human review")
    return True


def test_no_auto_approval_generated() -> bool:
    package = build_legal_review_package(
        build_mock_entity_results(),
        run_id="run-legal-test",
        script_id="script-legal-test",
    )

    if package.overall_decision != ReviewDecision.NEEDS_REVIEW:
        print("FAILED: overall decision should default to NEEDS_REVIEW")
        return False

    for record in package.entity_reviews:
        if record.decision != ReviewDecision.NEEDS_REVIEW:
            print(f"FAILED: entity {record.entity_name} was auto-decided as {record.decision}")
            return False
        if record.reviewer is not None:
            print(f"FAILED: entity {record.entity_name} has reviewer without human action")
            return False

    if all_required_reviews_resolved(package):
        print("FAILED: required reviews should not be resolved without human input")
        return False

    print("PASSED: no approval is automatically generated")
    return True


def test_explicit_approval_recorded() -> bool:
    package = build_legal_review_package(
        build_mock_entity_results(),
        run_id="run-legal-test",
        script_id="script-legal-test",
    )

    updated = record_entity_decision(
        package,
        entity_id="e-high",
        decision=ReviewDecision.APPROVED,
        reviewer=REVIEWER,
        comment="Reviewed brand usage; approved with conditions.",
    )

    record = next(r for r in updated.entity_reviews if r.entity_id == "e-high")
    if record.decision != ReviewDecision.APPROVED:
        print("FAILED: approval not recorded")
        return False
    if record.reviewer != REVIEWER:
        print("FAILED: reviewer not recorded")
        return False
    if record.reviewed_at is None:
        print("FAILED: reviewed_at not recorded")
        return False
    if record.ai_risk_level != RiskLevel.HIGH_RISK:
        print("FAILED: original AI risk classification was overwritten")
        return False

    print("PASSED: explicit approval is recorded with audit trail")
    return True


def test_explicit_blocking_recorded() -> bool:
    package = build_legal_review_package(
        build_mock_entity_results(),
        run_id="run-legal-test",
        script_id="script-legal-test",
    )

    updated = record_entity_decision(
        package,
        entity_id="e-high",
        decision=ReviewDecision.BLOCKED,
        reviewer=REVIEWER,
        comment="Prominent brand usage blocked pending clearance.",
    )

    record = next(r for r in updated.entity_reviews if r.entity_id == "e-high")
    if record.decision != ReviewDecision.BLOCKED:
        print("FAILED: blocking not recorded")
        return False
    if record.ai_risk_level != RiskLevel.HIGH_RISK:
        print("FAILED: original AI risk classification was overwritten on block")
        return False

    print("PASSED: explicit blocking is recorded")
    return True


def test_needs_review_remains_unresolved() -> bool:
    package = build_legal_review_package(
        build_mock_entity_results(),
        run_id="run-legal-test",
        script_id="script-legal-test",
    )

    pending = get_pending_required_reviews(package)
    if len(pending) != 1 or pending[0].entity_id != "e-high":
        print(f"FAILED: expected 1 pending high-risk review, got {len(pending)}")
        return False

    try:
        record_overall_decision(
            package,
            decision=ReviewDecision.APPROVED,
            reviewer=REVIEWER,
        )
        print("FAILED: run approval should be blocked while reviews are unresolved")
        return False
    except ValueError:
        pass

    unresolved = next(r for r in package.entity_reviews if r.entity_id == "e-high")
    if unresolved.decision != ReviewDecision.NEEDS_REVIEW:
        print("FAILED: NEEDS_REVIEW should remain unresolved")
        return False

    print("PASSED: NEEDS_REVIEW remains unresolved and blocks run approval")
    return True


def test_ai_classification_preserved_after_decision() -> bool:
    result = make_entity_result(
        "e-preserve",
        "McDonald's",
        EntityType.BUSINESS,
        RiskLevel.HIGH_RISK,
        requires_human_review=True,
    )
    original = build_entity_review_record(result)
    original_ai = original.ai_risk_level
    original_reasoning = original.ai_reasoning

    package = build_legal_review_package(
        {EntityType.BUSINESS: [result]},
        run_id="run-preserve",
        script_id="script-preserve",
    )
    updated = record_entity_decision(
        package,
        entity_id="e-preserve",
        decision=ReviewDecision.APPROVED,
        reviewer=REVIEWER,
        comment="Approved.",
    )
    record = updated.entity_reviews[0]

    if record.ai_risk_level != original_ai:
        print("FAILED: ai_risk_level changed after human decision")
        return False
    if record.ai_reasoning != original_reasoning:
        print("FAILED: ai_reasoning changed after human decision")
        return False
    if record.decision != ReviewDecision.APPROVED:
        print("FAILED: human decision not recorded separately")
        return False

    print("PASSED: original AI classification preserved after human decision")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Legal Review Workflow")
    print("=" * 60 + "\n")

    tests = [
        test_high_risk_requires_human_review,
        test_no_auto_approval_generated,
        test_explicit_approval_recorded,
        test_explicit_blocking_recorded,
        test_needs_review_remains_unresolved,
        test_ai_classification_preserved_after_decision,
    ]

    results = [test() for test in tests]

    print("\n" + "=" * 60)
    if all(results):
        print("ALL TESTS PASSED")
        sys.exit(0)

    print("TESTS FAILED")
    sys.exit(1)
