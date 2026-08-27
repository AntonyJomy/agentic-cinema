"""
agents/risk_scoring_agent.py

Risk Scoring Agent for screenplay E&O clearance.

Receives ONE grounded Entity plus its specialist ResearchResult and applies
the project rubric to produce a RiskResult (clear / caution / high_risk).

This agent does NOT perform web research or call Parallel MCP.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from schemas.entities import Entity, EntityType, RiskCategory
from schemas.research_result import ResearchResult
from schemas.risk_result import RiskResult
from agents.model_config import get_gemini_model

load_dotenv()

if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

MODEL = get_gemini_model()

RUBRIC_BY_CATEGORY = {
    RiskCategory.BUSINESS_LOCATION: """
BUSINESS / LOCATION
- CLEAR: No credible real-world match is found.
- CAUTION: A similar or ambiguous real-world match exists, but evidence does
  not establish a strong exact match.
- HIGH_RISK: A real identifiable business/location strongly matches the
  screenplay reference and the screenplay usage creates a meaningful clearance
  concern.
""",
    RiskCategory.NAME_COLLISION: """
CHARACTER NAME
- CLEAR: No credible identifiable real person matching the character name is found.
- CAUTION: A possible or ambiguous real-person match exists.
- HIGH_RISK: A real, identifiable person strongly matches the character name
  AND the screenplay portrayal/context creates a meaningful concern.
""",
    RiskCategory.MUSIC_RIGHTS: """
MUSIC
- CLEAR: No identifiable real musical work is established.
- CAUTION: The reference is ambiguous or insufficiently identified.
- HIGH_RISK: A specific real musical work is clearly identified and the
  screenplay uses or references it in a way requiring further rights review.
""",
    RiskCategory.TRADEMARK_BRAND: """
TRADEMARK / BRAND
- CLEAR: No credible real brand/trademark match.
- CAUTION: Possible or partial match.
- HIGH_RISK: Exact real brand/trademark is clearly identified and used
  prominently or in a potentially sensitive context.
""",
    RiskCategory.PII_EXPOSURE: """
ADDRESS / PII
- CLEAR: No credible real-world association is established.
- CAUTION: Possible real-world association but insufficient evidence.
- HIGH_RISK: The screenplay contains a real identifiable location/address or
  sensitive information that creates a meaningful privacy/E&O concern.
""",
    RiskCategory.LITERARY_RIGHTS: """
LITERARY REFERENCE
- CLEAR: No identifiable published work/reference is established.
- CAUTION: Possible or ambiguous literary reference.
- HIGH_RISK: A specific identifiable copyrighted/published work is clearly
  referenced and the usage warrants rights review.
""",
    RiskCategory.DEFAMATION_RISK: """
REAL PUBLIC FIGURE / DEFAMATION
- CLEAR: No credible identifiable real person match or no meaningful concern
  from the screenplay context.
- CAUTION: Possible or ambiguous real-person match or sensitive context.
- HIGH_RISK: A real identifiable person strongly matches AND the screenplay
  portrayal/context creates a meaningful concern.
""",
}


def build_scoring_prompt(entity: Entity, research_result: ResearchResult) -> str:
    """Build the user message for the risk scoring agent."""
    rubric = RUBRIC_BY_CATEGORY.get(
        entity.risk_category,
        "Apply the most relevant rubric based on entity_type and evidence.",
    )
    return (
        "RISK SCORING REQUEST\n\n"
        "Score the following grounded Entity using ONLY the supplied specialist "
        "research. Do NOT perform new research.\n\n"
        "## ENTITY\n\n"
        f"{entity.model_dump_json(indent=2)}\n\n"
        "## SPECIALIST RESEARCH RESULT\n\n"
        f"{research_result.model_dump_json(indent=2)}\n\n"
        "## RUBRIC FOR THIS ENTITY\n\n"
        f"{rubric}\n\n"
        "Return a RiskResult with:\n"
        "- entity_id, entity_name, entity_type from the Entity\n"
        "- risk_level: clear, caution, or high_risk (based on evidence, NOT research confidence)\n"
        "- triggered_rule: the specific rubric rule that applied\n"
        "- reasoning: explain why this risk level was assigned\n"
        "- evidence: supporting items from the research citations (do NOT invent URLs)\n"
        "- research_confidence: copy from ResearchResult.confidence\n"
        f"- requires_human_review: set true if Entity.requires_human_review is "
        f"{entity.requires_human_review}; never set false if Entity already requires review"
    )


risk_scorer = LlmAgent(
    model=MODEL,
    name="risk_scorer",
    description=(
        "Applies the clearance rubric to a grounded Entity and its specialist "
        "ResearchResult to produce a RiskResult."
    ),
    instruction="""
You are the Risk Scoring Agent in a screenplay E&O clearance system.

OBJECTIVE
Given ONE grounded Entity and its specialist ResearchResult, apply the project
rubric and assign exactly one risk level:
- clear
- caution
- high_risk

You are a SCORING agent only. Do NOT perform web research. Do NOT call Parallel.
Do NOT invent evidence or citations not present in the ResearchResult.

CONFIDENCE DISTINCTION (CRITICAL)
- Entity.confidence = extraction confidence (ignore for risk scoring)
- ResearchResult.confidence = research/evidence confidence (record it, do NOT
  treat it as the risk level)
- risk_level = rubric outcome based on entity, screenplay context, research
  finding, and citations

A high research confidence does NOT automatically mean high_risk.
Example: research confidence 0.98 with finding "no real-world match found"
should typically be clear, not high_risk.

PROCESS
1. Read the Entity: name, entity_type, risk_category, context, location,
   requires_human_review.
2. Read the ResearchResult: finding, confidence, citations, status.
3. Apply the rubric for the entity's risk_category / entity_type.
4. Base the decision on evidence in the finding and citations — not entity type alone.
5. Select the single best rubric rule as triggered_rule.
6. Write clear reasoning answering: "Why did this entity receive this risk level?"
7. Copy supporting evidence from ResearchResult.citations into evidence.
   Do NOT invent new sources.
8. Set research_confidence from ResearchResult.confidence.
9. Preserve requires_human_review:
   - If Entity.requires_human_review is true, output requires_human_review=true.
   - Never downgrade an existing human-review requirement to false.

IMPORTANT
- This is an initial project rubric, NOT a legal conclusion.
- Every output MUST include triggered_rule and reasoning.
- Do NOT confuse research confidence with risk level.
- Do NOT use web search or external tools.
""",
    output_schema=RiskResult,
)


def finalize_risk_result(entity: Entity, agent_output: RiskResult) -> RiskResult:
    """
    Merge agent output with immutable Entity fields.

    Preserves requires_human_review from the Entity and ensures identity fields
    match the source Entity.
    """
    updates: dict = {
        "entity_id": entity.entity_id,
        "entity_name": entity.name,
        "entity_type": entity.entity_type,
    }
    if entity.requires_human_review:
        updates["requires_human_review"] = True
    return agent_output.model_copy(update=updates)
