"""
tests/test_deterministic_grounding.py

Rigorous unit tests for gatekeeper.deterministic_grounding (no LLM / API keys).
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from gatekeeper.deterministic_grounding import (  # noqa: E402
    ground_entities,
    is_entity_grounded,
    normalize_grounding_text,
)
from orchestrator import run_grounding_check  # noqa: E402
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


def _meta() -> ExtractionMetadata:
    return ExtractionMetadata(
        model_used="test",
        extracted_at=datetime.now(timezone.utc),
        extraction_agent_version="0.1.0",
        total_pages_scanned=1,
    )


def _entity(
    entity_id: str,
    name: str,
    entity_type: EntityType,
    line: str,
    confidence: float = 0.9,
) -> Entity:
    return Entity(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        context=line,
        location=ScriptLocation(scene_number=1, line_excerpt=line),
        confidence=confidence,
    )


def _entities(items: list[Entity], run_id: str = "run-det-grounding") -> Entities:
    return Entities(
        run_id=run_id,
        script_id="script-det-grounding",
        script_title="Deterministic Grounding Test",
        entities=items,
        metadata=_meta(),
    )


def build_test_entities() -> Entities:
    return _entities(
        [
            _entity(
                "entity-mcdonalds",
                "McDonald's",
                EntityType.BUSINESS,
                "John walks into McDonald's and orders a coffee.",
            ),
            _entity(
                "entity-love-story",
                "Love Story",
                EntityType.SONG,
                "Sarah listens to Love Story while sitting at the table.",
            ),
            _entity(
                "entity-elon-musk",
                "Elon Musk",
                EntityType.CHARACTER_NAME,
                "John says he saw Elon Musk on television.",
            ),
            _entity(
                "entity-coca-cola",
                "Coca-Cola",
                EntityType.LOGO_BRAND,
                "A Coca-Cola logo appears on a billboard outside the cafe.",
                confidence=0.7,
            ),
        ]
    )


# --- normalize ---


def test_normalize_handles_apostrophes():
    assert normalize_grounding_text("McDonald’s") == normalize_grounding_text(
        "McDonald's"
    )


def test_normalize_collapses_whitespace_and_case():
    assert normalize_grounding_text("  Love   STORY\n") == "love story"


def test_normalize_empty():
    assert normalize_grounding_text("") == ""


# --- is_entity_grounded ---


def test_is_entity_grounded_by_name():
    entity = _entity(
        "e1",
        "McDonald's",
        EntityType.BUSINESS,
        "some unrelated excerpt that is wrong",
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is True


def test_is_entity_grounded_case_insensitive_name():
    entity = _entity(
        "e1",
        "mcdonald's",
        EntityType.BUSINESS,
        "wrong excerpt here",
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is True


def test_is_entity_grounded_curly_apostrophe_name():
    entity = _entity(
        "e1",
        "McDonald’s",  # curly apostrophe
        EntityType.BUSINESS,
        "wrong excerpt here",
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is True


def test_is_entity_grounded_rejects_missing():
    entity = _entity(
        "e2",
        "Coca-Cola",
        EntityType.LOGO_BRAND,
        "A Coca-Cola logo appears on a billboard outside the cafe.",
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is False


def test_is_entity_grounded_via_excerpt_when_name_typo():
    """Name mistyped but line_excerpt is accurate → still grounded."""
    entity = _entity(
        "e3",
        "McDonelds",  # typo — not in script
        EntityType.BUSINESS,
        "John walks into McDonald's and orders a coffee.",
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is True


def test_short_excerpt_alone_does_not_false_positive():
    """Tiny excerpt must not ground if name is absent."""
    entity = _entity(
        "e4",
        "TotallyFakeBrand",
        EntityType.LOGO_BRAND,
        "orders",  # appears in script but shorter than threshold
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is False


def test_empty_screenplay_rejects_all():
    entity = _entity(
        "e5",
        "McDonald's",
        EntityType.BUSINESS,
        "John walks into McDonald's and orders a coffee.",
    )
    assert is_entity_grounded(entity, "") is False
    assert is_entity_grounded(entity, "   ") is False


def test_no_substring_false_positive_inside_longer_word():
    """'Ann' must not match inside 'Banner'."""
    screenplay = "INT. STREET - DAY\n\nA Banner hangs over the road.\n"
    entity = _entity(
        "e6",
        "Ann",
        EntityType.CHARACTER_NAME,
        "Someone named Ann walks by.",  # excerpt not in screenplay
    )
    assert is_entity_grounded(entity, screenplay) is False


def test_multi_word_name_requires_full_phrase():
    entity = _entity(
        "e7",
        "Elon Musk",
        EntityType.CHARACTER_NAME,
        "wrong excerpt",
    )
    assert is_entity_grounded(entity, TEST_SCREENPLAY) is True

    # Only first token present should not count as the full name
    partial_script = "INT. OFFICE\n\nElon speaks on a screen.\n"
    assert is_entity_grounded(entity, partial_script) is False


# --- ground_entities ---


def test_ground_entities_filters_ungrounded():
    input_entities = build_test_entities()
    filtered, grounded, rejected = ground_entities(TEST_SCREENPLAY, input_entities)

    grounded_names = {e.name for e in grounded}
    rejected_names = {e.name for e in rejected}

    assert grounded_names == {"McDonald's", "Love Story", "Elon Musk"}
    assert rejected_names == {"Coca-Cola"}
    assert filtered.entity_count == 3
    assert filtered.run_id == input_entities.run_id
    assert filtered.script_id == input_entities.script_id
    assert filtered.script_title == input_entities.script_title

    original_by_id = {e.entity_id: e for e in input_entities.entities}
    for entity in grounded:
        assert entity.model_dump() == original_by_id[entity.entity_id].model_dump()


def test_ground_entities_empty_input():
    empty = _entities([])
    filtered, grounded, rejected = ground_entities(TEST_SCREENPLAY, empty)
    assert filtered.entity_count == 0
    assert grounded == []
    assert rejected == []
    assert filtered.run_id == empty.run_id


def test_ground_entities_all_rejected():
    items = [
        _entity(
            "a",
            "Pepsi",
            EntityType.LOGO_BRAND,
            "A Pepsi can sits on the counter.",
        ),
        _entity(
            "b",
            "Starbucks",
            EntityType.BUSINESS,
            "They meet at Starbucks later.",
        ),
    ]
    batch = _entities(items)
    filtered, grounded, rejected = ground_entities(TEST_SCREENPLAY, batch)
    assert grounded == []
    assert len(rejected) == 2
    assert filtered.entity_count == 0


def test_ground_entities_all_grounded():
    items = [
        _entity(
            "a",
            "McDonald's",
            EntityType.BUSINESS,
            "John walks into McDonald's and orders a coffee.",
        ),
        _entity(
            "b",
            "Love Story",
            EntityType.SONG,
            "Sarah listens to Love Story while sitting at the table.",
        ),
    ]
    batch = _entities(items)
    filtered, grounded, rejected = ground_entities(TEST_SCREENPLAY, batch)
    assert len(grounded) == 2
    assert rejected == []
    assert filtered.entity_count == 2


def test_ground_entities_preserves_requires_human_review():
    entity = Entity(
        entity_id="pf-1",
        name="Elon Musk",
        entity_type=EntityType.REAL_PUBLIC_FIGURE,
        context="John says he saw Elon Musk on television.",
        location=ScriptLocation(
            scene_number=1,
            line_excerpt="John says he saw Elon Musk on television.",
        ),
        confidence=0.9,
    )
    assert entity.requires_human_review is True
    filtered, grounded, rejected = ground_entities(TEST_SCREENPLAY, _entities([entity]))
    assert len(grounded) == 1
    assert grounded[0].requires_human_review is True
    assert rejected == []


def test_pdf_style_page_markers_still_match():
    """Extracted PDF text often includes page banners."""
    pdf_like = (
        "\n\n--- Page 1 ---\n"
        "INT. CAFE - DAY\n"
        "John walks into McDonald's and orders a coffee.\n"
        "\n\n--- Page 2 ---\n"
        "Sarah listens to Love Story while sitting at the table.\n"
    )
    entity = _entity(
        "pdf-1",
        "McDonald's",
        EntityType.BUSINESS,
        "John walks into McDonald's and orders a coffee.",
    )
    assert is_entity_grounded(entity, pdf_like) is True


# --- orchestrator wiring ---


def test_run_grounding_check_uses_deterministic_path():
    input_entities = build_test_entities()
    result = asyncio.run(
        run_grounding_check(TEST_SCREENPLAY, input_entities, user_id="rigor_test")
    )
    names = {e.name for e in result.entities}
    assert names == {"McDonald's", "Love Story", "Elon Musk"}
    assert "Coca-Cola" not in names


def test_run_grounding_check_empty_entities_noop():
    empty = _entities([])
    result = asyncio.run(
        run_grounding_check(TEST_SCREENPLAY, empty, user_id="rigor_test")
    )
    assert result.entity_count == 0
    assert result.run_id == empty.run_id
