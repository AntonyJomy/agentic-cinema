"""
agents/grounding_check_agent.py

The Grounding Check Agent validates that every entity extracted from a
screenplay is actually supported by the original screenplay text.

It reads an `Entities` object plus the screenplay and returns a filtered
`Entities` object containing only grounded entities. It does NOT perform
web research, legal risk assessment, or Parallel lookups.
"""
import json
import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from schemas.entities import Entities

load_dotenv()


def build_grounding_prompt(screenplay_text: str, entities: Entities) -> str:
    """Build the user message for the grounding check agent."""
    entities_json = entities.model_dump_json(indent=2)
    return (
        "GROUNDING CHECK REQUEST\n\n"
        "Validate EVERY extracted entity against the screenplay below.\n"
        "The screenplay is the authoritative source for grounding.\n\n"
        "## SCREENPLAY (authoritative source)\n\n"
        f"{screenplay_text}\n\n"
        "## EXTRACTED ENTITIES (validate each)\n\n"
        f"{entities_json}\n\n"
        "Return an Entities object containing ONLY entities that are grounded "
        "in the screenplay. Preserve run_id, script_id, script_title, and "
        "metadata from the input. For each retained entity, preserve the "
        "exact entity_id and all original Entity fields unchanged."
    )


grounding_checker = LlmAgent(
    model="gemini-3.6-flash",
    name="grounding_checker",
    description=(
        "Validates extracted screenplay entities against the original "
        "screenplay text and filters out unsupported entities."
    ),
    instruction="""
You are the Grounding Check Agent for a screenplay E&O clearance system.

Your job is SCREENPLAY VALIDATION — not web research, not legal risk analysis.

OBJECTIVE
Verify that every entity in the input Entities object is actually supported
by the original screenplay text. The Extraction Agent may over-flag entities;
your job is to confirm or reject each one against the screenplay.

WHAT "GROUNDED" MEANS
An entity is grounded when there is sufficient evidence in the screenplay
that the entity actually appears there. Grounding is about the SCREENPLAY,
not the real world.

For each entity:
1. Read the entity name, entity_type, context, and ScriptLocation.
2. Locate relevant text in the screenplay.
3. Determine whether the entity name is supported by the screenplay.
4. Compare the extracted context with the screenplay — both the name AND
   context should be reasonably supported.
5. Use ScriptLocation (page_number, scene_number, line_excerpt) when helpful.

TEXT MATCHING
Account for reasonable differences:
- capitalization
- punctuation
- possessives
- quotation marks
- screenplay formatting
- minor whitespace differences

Do NOT invent semantic matches that are not supported by the screenplay.

DECISIONS
- GROUNDED: retain the entity in the output Entities list.
- NOT GROUNDED: omit the entity from the output Entities list.

OUTPUT CONTRACT
Return an Entities object with:
- run_id, script_id, script_title, metadata — copied from the input
- entities — ONLY grounded entities

For each retained entity:
- Preserve the exact entity_id from the input
- Do NOT modify name, entity_type, risk_category, context, location,
  confidence, requires_human_review, or extraction_notes
- Do NOT overwrite confidence — it represents extraction confidence, not
  grounding confidence

IMPORTANT
- Validate EVERY input entity (grounded entities stay, others are omitted)
- Do NOT add new entities that were not in the input
- Do NOT determine legal risk, clearance status, or real-world facts
- Do NOT use web search or external tools
""",
    output_schema=Entities,
)


def apply_grounding_filter(
    original: Entities,
    agent_output: Entities,
) -> tuple[Entities, list, list]:
    """
    Merge agent grounding decisions with original entity objects.

    The agent decides which entity_ids to retain; original Entity objects
    are preserved unchanged to avoid LLM field drift.

    Returns:
        (filtered_entities, grounded_entities, rejected_entities)
    """
    retained_ids = {entity.entity_id for entity in agent_output.entities}
    original_ids = {entity.entity_id for entity in original.entities}

    grounded = [entity for entity in original.entities if entity.entity_id in retained_ids]
    rejected = [entity for entity in original.entities if entity.entity_id not in retained_ids]

    # Agent may hallucinate extra entity_ids — ignore anything not in original.
    unknown_ids = retained_ids - original_ids
    if unknown_ids:
        grounded = [entity for entity in grounded if entity.entity_id in original_ids]

    filtered = original.model_copy(update={"entities": grounded})
    return filtered, grounded, rejected
