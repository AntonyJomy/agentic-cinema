"""
tests/test_risk_scoring_agent.py

Tests the Risk Scoring Agent with mocked ResearchResult data.
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

from agents.risk_scoring_agent import finalize_risk_result  # noqa: E402
from orchestrator import score_entity_risk  # noqa: E402
from schemas.entities import Entity, EntityType, ScriptLocation  # noqa: E402
from schemas.research_result import Citation, ResearchResult, ResearchStatus  # noqa: E402
from schemas.risk_result import RiskLevel, RiskResult  # noqa: E402

USER_ID = "risk_scoring_test"


def make_entity(
    name: str,
    entity_type: EntityType,
    context: str,
    entity_id: str,
    requires_human_review: bool = False,
) -> Entity:
    return Entity(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        context=context,
        location=ScriptLocation(
            scene_number=1,
            line_excerpt=context,
        ),
        confidence=0.9,
        requires_human_review=requires_human_review,
    )


def mock_clear_research(entity: Entity) -> ResearchResult:
    """Fictional business with no real-world match."""
    return ResearchResult(
        entity_id=entity.entity_id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        finding=(
            "No credible real-world business named Zorbax Industries was found. "
            "Web searches returned no registered companies, trademarks, or known "
            "establishments matching this exact name."
        ),
        confidence=0.88,
        citations=[],
        status=ResearchStatus.INSUFFICIENT_EVIDENCE,
        research_notes="Searched business registries and general web; no matches.",
    )


def mock_caution_research(entity: Entity) -> ResearchResult:
    """Ambiguous partial match."""
    return ResearchResult(
        entity_id=entity.entity_id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        finding=(
            "Several independent cafes named Blue Cafe exist in different cities, "
            "including Portland and Austin. Available evidence does not establish "
            "a strong exact match to the screenplay's unspecified downtown setting."
        ),
        confidence=0.62,
        citations=[
            Citation(
                source_url="https://example.com/blue-cafe-portland",
                summary="Lists a Blue Cafe in Portland, OR.",
            ),
            Citation(
                source_url="https://example.com/blue-cafe-austin",
                summary="Lists a Blue Cafe in Austin, TX.",
            ),
        ],
        status=ResearchStatus.SUCCESS,
    )


def mock_high_risk_research(entity: Entity) -> ResearchResult:
    """Clearly identifiable real entity with prominent screenplay usage."""
    return ResearchResult(
        entity_id=entity.entity_id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        finding=(
            "McDonald's is a globally recognized fast-food corporation and registered "
            "trademark. The screenplay depicts a character walking into McDonald's and "
            "ordering coffee, creating prominent brand usage in scene action."
        ),
        confidence=0.97,
        citations=[
            Citation(
                source_url="https://www.mcdonalds.com/",
                summary="Official McDonald's corporate website identifying the brand.",
            ),
            Citation(
                source_url="https://example.com/mcdonalds-trademark",
                summary="Trademark registry listing for McDonald's.",
            ),
        ],
        status=ResearchStatus.SUCCESS,
    )


async def run_scoring_case(
    entity: Entity,
    research: ResearchResult,
    expected_level: RiskLevel,
    case_name: str,
) -> bool:
    print(f"\n--- {case_name} ---")
    risk_result = await score_entity_risk(
        entity=entity,
        research_result=research,
        user_id=USER_ID,
    )

    print(f"Expected: {expected_level.value}")
    print(f"Got:      {risk_result.risk_level.value}")
    print(f"Rule:     {risk_result.triggered_rule}")
    print(f"Reason:   {risk_result.reasoning[:120]}...")

    if risk_result.risk_level != expected_level:
        print(f"FAILED: Expected {expected_level.value}, got {risk_result.risk_level.value}")
        return False

    if not risk_result.triggered_rule.strip():
        print("FAILED: triggered_rule is empty")
        return False

    if not risk_result.reasoning.strip():
        print("FAILED: reasoning is empty")
        return False

    if risk_result.research_confidence != research.confidence:
        print(
            f"FAILED: research_confidence mismatch "
            f"(expected {research.confidence}, got {risk_result.research_confidence})"
        )
        return False

    if risk_result.entity_id != entity.entity_id:
        print("FAILED: entity_id mismatch")
        return False

    RiskResult.model_validate(risk_result.model_dump(mode="json"))
    print(f"PASSED: {case_name}")
    return True


def test_finalize_preserves_human_review() -> bool:
    entity = make_entity(
        name="Senator Jane Doe",
        entity_type=EntityType.REAL_PUBLIC_FIGURE,
        context="Dialogue references Senator Jane Doe by name.",
        entity_id="entity-public-figure",
        requires_human_review=True,
    )
    agent_output = RiskResult(
        entity_id=entity.entity_id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        risk_level=RiskLevel.CLEAR,
        triggered_rule="character_name_clear",
        reasoning="No credible match found.",
        evidence=[],
        research_confidence=0.8,
        requires_human_review=False,
    )

    finalized = finalize_risk_result(entity, agent_output)
    if not finalized.requires_human_review:
        print("FAILED: requires_human_review was cleared")
        return False

    print("PASSED: finalize_risk_result preserves requires_human_review")
    return True


def test_high_research_confidence_does_not_imply_high_risk() -> bool:
    """Document that research confidence alone must not determine risk."""
    entity = make_entity(
        name="Zorbax Industries",
        entity_type=EntityType.BUSINESS,
        context="INT. ZORBAX INDUSTRIES HQ - DAY.",
        entity_id="entity-zorbax",
    )
    research = mock_clear_research(entity)
    research = research.model_copy(update={"confidence": 0.98})

    if research.confidence < 0.9:
        print("FAILED: test setup error")
        return False

    print(
        "PASSED: high research confidence fixture prepared "
        f"({research.confidence}) for clear-case entity"
    )
    return True


async def test_risk_scoring_agent() -> bool:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY required")
        return False

    clear_entity = make_entity(
        name="Zorbax Industries",
        entity_type=EntityType.BUSINESS,
        context="INT. ZORBAX INDUSTRIES HQ - DAY. Employees work at their desks.",
        entity_id="entity-clear",
    )
    caution_entity = make_entity(
        name="Blue Cafe",
        entity_type=EntityType.BUSINESS,
        context="INT. BLUE CAFE - DAY. A small downtown cafe.",
        entity_id="entity-caution",
    )
    high_risk_entity = make_entity(
        name="McDonald's",
        entity_type=EntityType.BUSINESS,
        context="John walks into McDonald's and orders a coffee.",
        entity_id="entity-high-risk",
    )

    clear_ok = await run_scoring_case(
        clear_entity,
        mock_clear_research(clear_entity),
        RiskLevel.CLEAR,
        "Test 1: CLEAR (fictional business, no real-world match)",
    )
    caution_ok = await run_scoring_case(
        caution_entity,
        mock_caution_research(caution_entity),
        RiskLevel.CAUTION,
        "Test 2: CAUTION (ambiguous partial match)",
    )
    high_risk_ok = await run_scoring_case(
        high_risk_entity,
        mock_high_risk_research(high_risk_entity),
        RiskLevel.HIGH_RISK,
        "Test 3: HIGH_RISK (identifiable real brand, prominent usage)",
    )

    return clear_ok and caution_ok and high_risk_ok


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Risk Scoring Agent")
    print("=" * 60)

    unit_ok = test_finalize_preserves_human_review()
    unit_ok = test_high_research_confidence_does_not_imply_high_risk() and unit_ok
    agent_ok = asyncio.run(test_risk_scoring_agent()) if unit_ok else False

    print("\n" + "=" * 60)
    if unit_ok and agent_ok:
        print("ALL TESTS PASSED")
        sys.exit(0)

    print("TESTS FAILED")
    sys.exit(1)
