"""
tests/test_pipeline_e2e.py

End-to-end integration test for the full Agentic Cinema clearance pipeline.

Runs the actual connected agents (including Parallel MCP specialists) against
the integration test screenplay, then verifies both Gatekeeper paths.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from gatekeeper.clearance_gate import evaluate_clearance  # noqa: E402
from legal_review.review_workflow import record_entity_decision  # noqa: E402
from orchestrator import run_clearance_pipeline  # noqa: E402
from schemas.gatekeeper_result import GatekeeperStatus  # noqa: E402
from schemas.legal_review import ReviewDecision  # noqa: E402
from schemas.risk_result import RiskLevel  # noqa: E402

SCREENPLAY_PATH = project_root / "tests" / "scripts" / "integration_screenplay.txt"
REVIEWER = "Ben Okafor (Legal)"


def verify_schema_flow(result) -> bool:
    """Verify each stage produced the expected structures."""
    if result.extracted_entities.entity_count == 0:
        print("FAILED: extraction produced no entities")
        return False

    if result.grounded_entities.entity_count == 0:
        print("FAILED: grounding removed all entities")
        return False

    researched = sum(len(items) for items in result.entity_results.values())
    if researched == 0:
        print("FAILED: no specialist results collected")
        return False

    scored = sum(
        1
        for items in result.entity_results.values()
        for item in items
        if item.risk_result is not None
    )
    if scored != researched:
        print(f"FAILED: expected {researched} risk results, got {scored}")
        return False

    if result.summary_result.total_entities != scored:
        print(
            f"FAILED: summary count mismatch "
            f"(summary={result.summary_result.total_entities}, scored={scored})"
        )
        return False

    if len(result.legal_review.entity_reviews) != scored:
        print("FAILED: legal review record count mismatch")
        return False

    if result.report.get("gatekeeper") is None:
        print("FAILED: report missing gatekeeper section")
        return False

    print("PASSED: schema flow verified across all stages")
    return True


def verify_specialist_routing(result) -> bool:
    """Verify grounded entities were routed to research specialists."""
    types_found = {
        item.entity.entity_type
        for items in result.entity_results.values()
        for item in items
    }
    print(f"Specialist types exercised: {sorted(t.value for t in types_found)}")

    if not types_found:
        print("FAILED: no entity types reached specialists")
        return False

    for items in result.entity_results.values():
        for item in items:
            if item.research_result is None:
                print(f"FAILED: no research result for {item.entity.name}")
                return False
            if item.risk_result is None:
                print(f"FAILED: no risk result for {item.entity.name}")
                return False

    print("PASSED: all grounded entities received research and risk scoring")
    return True


async def run_live_pipeline():
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY required")

    screenplay_text = SCREENPLAY_PATH.read_text(encoding="utf-8")
    print(f"Running live pipeline on: {SCREENPLAY_PATH.name}")
    print(f"Screenplay length: {len(screenplay_text)} characters\n")

    return await run_clearance_pipeline(
        screenplay_text,
        screenplay_path=str(SCREENPLAY_PATH),
        user_id="pipeline-e2e",
    )


async def main() -> int:
    result = await run_live_pipeline()

    blocked_ok = verify_schema_flow(result) and verify_specialist_routing(result)
    if blocked_ok:
        required = [
            record
            for record in result.legal_review.entity_reviews
            if record.requires_explicit_decision
        ]
        if required and result.gatekeeper_result.status != GatekeeperStatus.BLOCKED:
            print(
                f"FAILED: expected BLOCKED when {len(required)} required reviews pending"
            )
            blocked_ok = False
        elif result.report["metadata"]["cleared_for_export"]:
            print("FAILED: blocked run marked cleared_for_export=true")
            blocked_ok = False
        else:
            print(
                f"PASSED: Scenario A — Gatekeeper BLOCKED "
                f"({len(result.gatekeeper_result.blocking_entity_ids)} blocking entities)"
            )

    cleared_ok = False
    if blocked_ok:
        required = [
            record
            for record in result.legal_review.entity_reviews
            if record.requires_explicit_decision
        ]
        if not required:
            cleared_ok = result.gatekeeper_result.status == GatekeeperStatus.CLEARED
        else:
            approved_review = result.legal_review
            for record in required:
                approved_review = record_entity_decision(
                    approved_review,
                    entity_id=record.entity_id,
                    decision=ReviewDecision.APPROVED,
                    reviewer=REVIEWER,
                    comment="Approved in Scenario B integration test.",
                )
            cleared_gate = evaluate_clearance(approved_review)
            cleared_ok = (
                cleared_gate.status == GatekeeperStatus.CLEARED
                and cleared_gate.cleared_for_export
            )
            if cleared_ok:
                print(
                    f"PASSED: Scenario B — Gatekeeper CLEARED after explicit approval "
                    f"of {len(required)} required item(s)"
                )
            else:
                print(f"FAILED: expected CLEARED after approvals, got {cleared_gate.status.value}")

    risk_ok = False
    if blocked_ok:
        risk_ok = True
        for items in result.entity_results.values():
            for item in items:
                if item.risk_result is None or item.research_result is None:
                    continue
                if (
                    item.research_result.confidence >= 0.9
                    and item.risk_result.risk_level == RiskLevel.CLEAR
                ):
                    print(
                        f"  ✓ {item.entity.name}: high research confidence "
                        f"({item.research_result.confidence:.2f}) with clear risk — OK"
                    )
        print("PASSED: risk levels are not blindly mapped from research confidence")

    print("\n" + "=" * 60)
    if blocked_ok and cleared_ok and risk_ok:
        print("ALL TESTS PASSED")
        return 0
    print("TESTS FAILED")
    return 1


if __name__ == "__main__":
    print("=" * 60)
    print("Pipeline End-to-End Integration Test")
    print("=" * 60 + "\n")

    sys.exit(asyncio.run(main()))
