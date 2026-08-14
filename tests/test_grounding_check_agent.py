"""
tests/test_grounding_check_agent.py

Tests the Grounding Check Agent against a small screenplay with one
deliberately ungrounded entity (Coca-Cola).
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv(os.path.join(project_root, ".env"))
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from agents.grounding_check_agent import (  # noqa: E402
    apply_grounding_filter,
    build_grounding_prompt,
    grounding_checker,
)
from orchestrator import run_grounding_check  # noqa: E402
from schemas.entities import (  # noqa: E402
    Entities,
    Entity,
    EntityType,
    ExtractionMetadata,
    ScriptLocation,
)
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

TEST_SCREENPLAY = """INT. CAFE - DAY

John walks into McDonald's and orders a coffee.

Sarah listens to Love Story while sitting at the table.

John says he saw Elon Musk on television.
"""

APP_NAME = "grounding_check_test"
USER_ID = "test_user"
SESSION_ID = "grounding_session"


def build_test_entities() -> Entities:
    """Build test entities including one not present in the screenplay."""
    metadata = ExtractionMetadata(
        model_used="gemini-3.6-flash",
        extracted_at=datetime.now(timezone.utc),
        extraction_agent_version="0.1.0",
        total_pages_scanned=1,
    )

    entities = [
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
            extraction_notes="Fast food restaurant mentioned in dialogue.",
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
            extraction_notes="Song title referenced in scene action.",
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
            extraction_notes="Public figure name spoken in dialogue.",
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
            extraction_notes="Brand flagged conservatively by extraction.",
        ),
    ]

    return Entities(
        run_id="run-grounding-test",
        script_id="script-grounding-test",
        script_title="Grounding Test Screenplay",
        entities=entities,
        metadata=metadata,
    )


async def test_grounding_check_agent() -> bool:
    """Run grounding check and verify grounded vs rejected entities."""
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY required")
        return False

    input_entities = build_test_entities()
    print(f"Input entities: {input_entities.entity_count}")
    print(f"Prompt length: {len(build_grounding_prompt(TEST_SCREENPLAY, input_entities))} chars\n")

    grounded_entities = await run_grounding_check(
        TEST_SCREENPLAY,
        input_entities,
        user_id=USER_ID,
    )

    try:
        validated = Entities.model_validate(grounded_entities.model_dump(mode="json"))
    except Exception as exc:
        print(f"FAILED: Output is not valid Entities schema: {exc}")
        return False

    grounded_names = {entity.name for entity in validated.entities}
    rejected_names = {
        entity.name
        for entity in input_entities.entities
        if entity.name not in grounded_names
    }

    print("\n--- Grounded entities ---")
    for entity in validated.entities:
        print(f"  • {entity.name} ({entity.entity_type.value})")

    print("\n--- Filtered entities ---")
    for name in rejected_names:
        print(f"  • {name}")

    expected_grounded = {"McDonald's", "Love Story", "Elon Musk"}
    expected_rejected = {"Coca-Cola"}

    if grounded_names != expected_grounded:
        print(
            f"\nFAILED: Expected grounded {expected_grounded}, got {grounded_names}"
        )
        return False

    if rejected_names != expected_rejected:
        print(
            f"\nFAILED: Expected rejected {expected_rejected}, got {rejected_names}"
        )
        return False

    original_by_id = {entity.entity_id: entity for entity in input_entities.entities}
    for entity in validated.entities:
        original = original_by_id[entity.entity_id]
        if entity.model_dump() != original.model_dump():
            print(
                f"\nFAILED: Entity fields changed for {entity.name}\n"
                f"Original: {original.model_dump()}\n"
                f"Returned: {entity.model_dump()}"
            )
            return False

    print("\nPASSED: Grounding check filtered entities correctly")
    print(f"Validated Entities object has {validated.entity_count} entities")
    return True


async def test_apply_grounding_filter_preserves_original_entities() -> bool:
    """Unit test for apply_grounding_filter without calling the LLM."""
    input_entities = build_test_entities()
    agent_output = input_entities.model_copy(
        update={
            "entities": [
                entity
                for entity in input_entities.entities
                if entity.entity_id != "entity-coca-cola"
            ]
        }
    )

    filtered, grounded, rejected = apply_grounding_filter(input_entities, agent_output)

    if len(grounded) != 3 or len(rejected) != 1:
        print(
            f"FAILED: Expected 3 grounded and 1 rejected, "
            f"got {len(grounded)} grounded and {len(rejected)} rejected"
        )
        return False

    if rejected[0].name != "Coca-Cola":
        print(f"FAILED: Expected Coca-Cola rejected, got {rejected[0].name}")
        return False

    if filtered.run_id != input_entities.run_id:
        print("FAILED: run_id was not preserved")
        return False

    print("PASSED: apply_grounding_filter preserves original entity objects")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Grounding Check Agent")
    print("=" * 60 + "\n")

    filter_ok = asyncio.run(test_apply_grounding_filter_preserves_original_entities())
    agent_ok = asyncio.run(test_grounding_check_agent()) if filter_ok else False

    print("\n" + "=" * 60)
    if filter_ok and agent_ok:
        print("ALL TESTS PASSED")
        sys.exit(0)

    print("TESTS FAILED")
    sys.exit(1)
