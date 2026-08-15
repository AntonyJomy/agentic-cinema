"""
tests/test_grounding_orchestrator_integration.py

Integration test: Extraction → Grounding → Specialist routing.

Verifies that a non-grounded entity does not reach specialist processing.
Uses mocked process_entity — no Parallel MCP calls.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv(os.path.join(project_root, ".env"))
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from orchestrator import (  # noqa: E402
    EntityResult,
    SPECIALISTS,
    process_entities,
    run_grounding_check,
)
from schemas.entities import (  # noqa: E402
    Entities,
    Entity,
    EntityType,
    ExtractionMetadata,
    ScriptLocation,
)

TEST_SCREENPLAY = """INT. CAFE - DAY

John walks into McDonald's and orders a coffee.

Sarah listens to Love Story while sitting at the table.

John says he saw Elon Musk on television.
"""


def build_test_entities() -> Entities:
    metadata = ExtractionMetadata(
        model_used="gemini-3.6-flash",
        extracted_at=datetime.now(timezone.utc),
        extraction_agent_version="0.1.0",
        total_pages_scanned=1,
    )

    return Entities(
        run_id="run-orchestrator-grounding-test",
        script_id="script-orchestrator-grounding-test",
        script_title="Grounding Orchestrator Test",
        entities=[
            Entity(
                entity_id="entity-mcdonalds",
                name="McDonald's",
                entity_type=EntityType.BUSINESS,
                context="John walks into McDonald's and orders a coffee.",
                location=ScriptLocation(
                    scene_number=1,
                    line_excerpt="John walks into McDonald's and orders a coffee.",
                ),
                confidence=0.95,
            ),
            Entity(
                entity_id="entity-love-story",
                name="Love Story",
                entity_type=EntityType.SONG,
                context="Sarah listens to Love Story while sitting at the table.",
                location=ScriptLocation(
                    scene_number=1,
                    line_excerpt="Sarah listens to Love Story while sitting at the table.",
                ),
                confidence=0.9,
            ),
            Entity(
                entity_id="entity-elon-musk",
                name="Elon Musk",
                entity_type=EntityType.CHARACTER_NAME,
                context="John says he saw Elon Musk on television.",
                location=ScriptLocation(
                    scene_number=1,
                    line_excerpt="John says he saw Elon Musk on television.",
                ),
                confidence=0.88,
            ),
            Entity(
                entity_id="entity-coca-cola",
                name="Coca-Cola",
                entity_type=EntityType.LOGO_BRAND,
                context="A Coca-Cola logo appears on a billboard outside the cafe.",
                location=ScriptLocation(
                    scene_number=1,
                    line_excerpt="A Coca-Cola logo appears on a billboard outside the cafe.",
                ),
                confidence=0.7,
            ),
        ],
        metadata=metadata,
    )


async def mock_process_entity(
    entity,
    specialist_config,
    user_id,
    entity_index,
    total_entities,
    on_progress=None,
):
    """Record specialist calls without invoking Parallel MCP."""
    return EntityResult(
        entity=entity,
        research_result=None,
        specialist_config=specialist_config,
        processing_time=0.0,
        success=True,
    )


async def test_grounding_orchestrator_integration() -> bool:
    extracted = build_test_entities()
    print(f"Extracted entities: {extracted.entity_count}")

    grounded = await run_grounding_check(TEST_SCREENPLAY, extracted, user_id="integration_test")
    print(f"Grounded entities: {grounded.entity_count}")

    grounded_names = {entity.name for entity in grounded.entities}
    if "Coca-Cola" in grounded_names:
        print("FAILED: Coca-Cola should have been filtered out by grounding")
        return False

    expected_grounded = {"McDonald's", "Love Story", "Elon Musk"}
    if grounded_names != expected_grounded:
        print(f"FAILED: Expected grounded {expected_grounded}, got {grounded_names}")
        return False

    processed_names: list[str] = []

    async def tracking_process_entity(
        entity,
        specialist_config,
        user_id,
        entity_index,
        total_entities,
        on_progress=None,
    ):
        processed_names.append(entity.name)
        return await mock_process_entity(
            entity,
            specialist_config,
            user_id,
            entity_index,
            total_entities,
            on_progress=on_progress,
        )

    with patch("orchestrator.process_entity", side_effect=tracking_process_entity):
        await process_entities(grounded, user_id="integration_test")

    if "Coca-Cola" in processed_names:
        print("FAILED: Coca-Cola reached specialist processing")
        return False

    if set(processed_names) != expected_grounded:
        print(
            f"FAILED: Expected specialists to process {expected_grounded}, "
            f"got {set(processed_names)}"
        )
        return False

    print("\nSpecialist calls (mocked, no Parallel):")
    for name in processed_names:
        print(f"  • {name}")

    print("\nPASSED: Grounded entities reached specialists; Coca-Cola did not")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Grounding Orchestrator Integration")
    print("=" * 60 + "\n")

    ok = asyncio.run(test_grounding_orchestrator_integration())

    print("\n" + "=" * 60)
    if ok:
        print("ALL TESTS PASSED")
        sys.exit(0)

    print("TESTS FAILED")
    sys.exit(1)
