"""
gatekeeper/deterministic_grounding.py

Deterministic screenplay grounding filter (no LLM).

Validates that extracted entities are supported by the original screenplay
text via normalized string matching on name and line_excerpt.

This replaces the LLM grounding step in the live pipeline for cost and
reliability. The original LLM agent remains in agents/grounding_check_agent.py
for reference / optional use.
"""
from __future__ import annotations

import re
import unicodedata

from schemas.entities import Entities, Entity


def normalize_grounding_text(value: str) -> str:
    """Normalize text for presence checks (case, punctuation, whitespace)."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_phrase(
    haystack: str,
    needle: str,
    *,
    require_boundaries: bool = True,
) -> bool:
    """Return True if normalized needle appears in normalized haystack.

    When require_boundaries is True (entity names), avoid substring false
    positives such as "Ann" matching inside "Banner".
    """
    if not needle:
        return False
    if not require_boundaries:
        return needle in haystack

    # Apostrophes are treated as part of the token (e.g. mcdonald's).
    pattern = r"(?<![\w'])" + re.escape(needle) + r"(?![\w'])"
    return re.search(pattern, haystack) is not None


def is_entity_grounded(entity: Entity, screenplay_text: str) -> bool:
    """Return True if the entity name or line_excerpt appears in the screenplay."""
    normalized_script = normalize_grounding_text(screenplay_text)
    if not normalized_script:
        return False

    name = normalize_grounding_text(entity.name)
    if _contains_phrase(normalized_script, name, require_boundaries=True):
        return True

    excerpt = normalize_grounding_text(entity.location.line_excerpt)
    # Require a meaningful excerpt so tiny fragments don't false-positive.
    # Excerpts are full lines — substring match is intentional.
    if len(excerpt) >= 8 and _contains_phrase(
        normalized_script, excerpt, require_boundaries=False
    ):
        return True

    return False


def ground_entities(
    screenplay_text: str,
    entities: Entities,
) -> tuple[Entities, list[Entity], list[Entity]]:
    """
    Filter entities to those grounded in the screenplay.

    Returns:
        (filtered_entities, grounded_list, rejected_list)

    Original Entity objects are preserved unchanged for grounded items.
    """
    grounded: list[Entity] = []
    rejected: list[Entity] = []

    for entity in entities.entities:
        if is_entity_grounded(entity, screenplay_text):
            grounded.append(entity)
        else:
            rejected.append(entity)

    filtered = entities.model_copy(update={"entities": grounded})
    return filtered, grounded, rejected
