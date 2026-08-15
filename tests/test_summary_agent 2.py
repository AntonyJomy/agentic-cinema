"""
tests/test_summary_agent.py

Tests the Summary Agent with mocked RiskResult data.
No Parallel MCP calls are made.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv(os.path.join(project_root, ".env"))
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from agents.summary_agent import (  # noqa: E402
    build_summary_prompt,
    compute_risk_counts,
    finalize_summary_result,
)
from orchestrator import EntityResult, SPECIALISTS, run_summary  # noqa: E402
from schemas.entities import Entity, EntityType, ScriptLocation  # noqa: E402
from schemas.research_result import Citation  # noqa: E402
from schemas.risk_result import RiskLevel, RiskResult  # noqa: E402
from schemas.summary_result import SummaryResult  # noqa: E402

USER_ID = "summary_test"
SCRIPT_TITLE = "Summary Test Screenplay"


def make_risk_result(
    entity_id: str,
    name: str,
    entity_type: EntityType,
    risk_level: RiskLevel,
    reasoning: str,
    triggered_rule: str,
    requires_human_review: bool = False,
) -> RiskResult:
    return RiskResult(
        entity_id=entity_id,
        entity_name=name,
        entity_type=entity_type,
        risk_level=risk_level,
        triggered_rule=triggered_rule,
        reasoning=reasoning,
        evidence=[
            Citation(
                source_url="https://example.com/source",
                summary=f"Evidence supporting assessment of {name}.",
            )
        ],
        research_confidence=0.85,
        requires_human_review=requires_human_review,
    )


def build_mock_risk_results() -> list[RiskResult]:
    """Two clear, two caution, one high-risk."""
    return [
        make_risk_result(
            "entity-clear-1",
            "Zorbax Industries",
            EntityType.BUSINESS,
            RiskLevel.CLEAR,
            "No credible real-world business named Zorbax Industries was found.",
            "business_clear_no_match",
        ),
        make_risk_result(
            "entity-clear-2",
            "Sunny's Workshop",
            EntityType.BUSINESS,
            RiskLevel.CLEAR,
            "No registered business or trademark matching Sunny's Workshop was identified.",
            "business_clear_no_match",
        ),
        make_risk_result(
            "entity-caution-1",
            "Blue Cafe",
            EntityType.BUSINESS,
            RiskLevel.CAUTION,
            "Several cafes named Blue Cafe exist, but no exact match to the screenplay context.",
            "business_caution_ambiguous_match",
            requires_human_review=True,
        ),
        make_risk_result(
            "entity-caution-2",
            "Harbor Street",
            EntityType.ADDRESS,
            RiskLevel.CAUTION,
            "Harbor Street exists in multiple cities; insufficient evidence for a specific match.",
            "address_caution_possible_association",
        ),
        make_risk_result(
            "entity-high-risk-1",
            "McDonald's",
            EntityType.BUSINESS,
            RiskLevel.HIGH_RISK,
            "McDonald's is a globally recognized corporation; the screenplay depicts prominent brand usage.",
            "business_high_risk_identifiable_match",
            requires_human_review=True,
        ),
    ]


def make_entity_result(risk_result: RiskResult) -> EntityResult:
    entity = Entity(
        entity_id=risk_result.entity_id,
        name=risk_result.entity_name,
        entity_type=risk_result.entity_type,
        context=f"Screenplay context for {risk_result.entity_name}.",
        location=ScriptLocation(
            scene_number=1,
            line_excerpt=f"Reference to {risk_result.entity_name}.",
        ),
        confidence=0.9,
        requires_human_review=risk_result.requires_human_review,
    )
    return EntityResult(
        entity=entity,
        research_result=None,
        specialist_config=SPECIALISTS[0],
        processing_time=0.0,
        success=True,
        risk_result=risk_result,
    )


def build_mock_entity_results() -> dict[EntityType, list[EntityResult]]:
    grouped: dict[EntityType, list[EntityResult]] = {}
    for risk_result in build_mock_risk_results():
        grouped.setdefault(risk_result.entity_type, []).append(
            make_entity_result(risk_result)
        )
    return grouped


def test_compute_risk_counts() -> bool:
    risk_results = build_mock_risk_results()
    counts = compute_risk_counts(risk_results)

    expected = {
        "total_entities": 5,
        "clear_count": 2,
        "caution_count": 2,
        "high_risk_count": 1,
    }
    if counts != expected:
        print(f"FAILED: Expected counts {expected}, got {counts}")
        return False

    print("PASSED: compute_risk_counts")
    return True


def test_finalize_summary_result() -> bool:
    risk_results = build_mock_risk_results()
    agent_output = SummaryResult(
        overall_summary="Test summary with incorrect counts.",
        total_entities=99,
        clear_count=99,
        caution_count=0,
        high_risk_count=0,
        priority_items=["McDonald's requires review."],
    )

    finalized = finalize_summary_result(risk_results, agent_output)
    if finalized.total_entities != 5:
        print(f"FAILED: total_entities should be 5, got {finalized.total_entities}")
        return False
    if finalized.clear_count != 2 or finalized.caution_count != 2:
        print("FAILED: clear/caution counts not corrected")
        return False
    if finalized.high_risk_count != 1:
        print(f"FAILED: high_risk_count should be 1, got {finalized.high_risk_count}")
        return False

    print("PASSED: finalize_summary_result enforces authoritative counts")
    return True


async def test_summary_agent() -> bool:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY required")
        return False

    risk_results = build_mock_risk_results()
    entity_results = build_mock_entity_results()

    print(f"Prompt length: {len(build_summary_prompt(risk_results, SCRIPT_TITLE))} chars\n")

    summary = await run_summary(
        entity_results,
        script_title=SCRIPT_TITLE,
        user_id=USER_ID,
    )

    SummaryResult.model_validate(summary.model_dump(mode="json"))

    if summary.total_entities != 5:
        print(f"FAILED: total_entities should be 5, got {summary.total_entities}")
        return False
    if summary.clear_count != 2:
        print(f"FAILED: clear_count should be 2, got {summary.clear_count}")
        return False
    if summary.caution_count != 2:
        print(f"FAILED: caution_count should be 2, got {summary.caution_count}")
        return False
    if summary.high_risk_count != 1:
        print(f"FAILED: high_risk_count should be 1, got {summary.high_risk_count}")
        return False

    combined_text = summary.overall_summary + " " + " ".join(summary.priority_items)
    if "McDonald's" not in combined_text:
        print("FAILED: high-risk entity McDonald's not highlighted")
        return False

    high_risk_reasoning = risk_results[-1].reasoning
    if high_risk_reasoning[:40] not in combined_text and "globally recognized" not in combined_text.lower():
        print("FAILED: supplied high-risk reasoning not reflected in summary")
        return False

    invented_marker = "InventedCorp XYZ"
    if invented_marker in combined_text:
        print("FAILED: summary appears to invent entities")
        return False

    priority_text = " ".join(summary.priority_items).lower()
    if "high_risk" not in priority_text and "high-risk" not in priority_text and "mcdonald" not in priority_text:
        print("FAILED: priority_items do not highlight high-risk finding")
        return False

    print("\n--- Summary ---")
    print(summary.overall_summary)
    print("\n--- Priority items ---")
    for item in summary.priority_items:
        print(f"  • {item}")

    print("\nPASSED: summary agent produces correct overview")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Summary Agent")
    print("=" * 60 + "\n")

    unit_ok = test_compute_risk_counts()
    unit_ok = test_finalize_summary_result() and unit_ok
    agent_ok = asyncio.run(test_summary_agent()) if unit_ok else False

    print("\n" + "=" * 60)
    if unit_ok and agent_ok:
        print("ALL TESTS PASSED")
        sys.exit(0)

    print("TESTS FAILED")
    sys.exit(1)
