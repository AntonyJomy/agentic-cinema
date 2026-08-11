"""
agents/character_name_specialist.py

Character Name Research Specialist for screenplay E&O clearance.

Receives ONE Entity with entity_type="character_name", researches whether
the name matches a real, identifiable person using Parallel Search MCP, and
returns a ResearchResult (finding + research confidence + citations).

Wrapped in LoopAgent for a confidence re-check (max ~2 iterations).

Follows the same structure as agents/business_specialist.py.

This agent does NOT perform legal risk scoring (clear/caution/high-risk),
defamation analysis, or clearance decisions.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools.exit_loop_tool import exit_loop

from gatekeeper.parallel_mcp import build_parallel_mcp_toolset
from schemas.research_result import ResearchResult

load_dotenv()

# Support both project conventions: agentic-cinema uses GEMINI_API_KEY;
# Google ADK expects GOOGLE_API_KEY.
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

MODEL = "gemini-3.6-flash"

# Session state keys shared inside the LoopAgent.
STATE_RESEARCH_RESULT = "character_research_result"
STATE_RECHECK_FEEDBACK = "character_confidence_recheck_feedback"

# Minimum research confidence that the re-check agent treats as "strong enough".
# This is research-evidence strength only — not a legal risk threshold.
MIN_EVIDENCE_CONFIDENCE = 0.75


character_research_agent = LlmAgent(
    model=MODEL,
    name="character_research_agent",
    description=(
        "Researches one character_name Entity via Parallel Search MCP and "
        "produces a structured ResearchResult with citations."
    ),
    instruction=f"""
You are the Character Name Research Specialist in a screenplay E&O clearance system.

OBJECTIVE:
Determine whether a character name extracted from a screenplay corresponds
to a real, identifiable person and gather reliable web evidence supporting
the finding.

The legal concern (for downstream agents, not you) is that a fictional
character could share a name with a real, identifiable individual.

You are a RESEARCH agent only. Do NOT assign legal risk labels
(clear / caution / high-risk). Do NOT make clearance decisions.
Do NOT perform defamation analysis or determine legal liability.

INPUT:
You receive exactly ONE Entity. It MUST have entity_type = "character_name".
Use the Entity fields dynamically:
- name (character name — never invent a different name)
- context (screenplay usage)
- location (page/scene/line_excerpt) when present
- confidence (extraction confidence — informational only; do not copy it as research confidence)

OPTIONAL PRIOR FEEDBACK (from the confidence re-check agent):
{{{STATE_RECHECK_FEEDBACK}?}}

If prior feedback is present and asks for a refined search, perform a more
targeted Parallel search addressing those gaps. Otherwise run a fresh search.

PROCESS:
1. Read the Entity. Confirm entity_type is character_name.
2. Build a research objective from the name and, only if available and useful,
   context cues (e.g. profession, city, or identifying details in the scene).
   Example: "Determine whether there is a real, identifiable person named
   Elon Musk. Find credible sources identifying this person and provide
   supporting evidence."
3. You MUST call the Parallel MCP web_search tool before answering.
   Prefer authoritative, relevant sources. Use web_fetch only if needed to
   clarify a promising source.
4. Do NOT rely on model memory for verification. Do NOT fabricate URLs or citations.
5. Produce a ResearchResult:
   - entity_name: from the Entity.name
   - entity_type: "character_name"
   - entity_id: from the Entity if present
   - finding: concise statement of what the evidence supports (e.g. whether
     a real identifiable person with this name was found)
   - confidence: your confidence in the RESEARCH FINDING (0.0–1.0), NOT legal risk
   - citations: real URLs/summaries from Parallel tool results only
   - status:
       - "success" when credible evidence supports a clear finding
       - "insufficient_evidence" when evidence is weak/ambiguous/absent
       - "tool_failure" when Parallel MCP search fails or returns unusable errors
   - research_notes: brief note on search approach / remaining uncertainty

FAILURE HANDLING:
- If Parallel fails: status=tool_failure, confidence low, finding states the tool/research failure, citations may be empty.
- If no credible evidence of a real identifiable person: status=insufficient_evidence, say so explicitly, do not guess.
""",
    tools=[build_parallel_mcp_toolset()],
    output_schema=ResearchResult,
    output_key=STATE_RESEARCH_RESULT,
)


character_confidence_recheck_agent = LlmAgent(
    model=MODEL,
    name="character_confidence_recheck_agent",
    description=(
        "Checks whether character-name research evidence is strong enough; "
        "exits the loop when sufficient, otherwise requests refined research."
    ),
    instruction=f"""
You are the Confidence Re-check Agent for the Character Name Research Specialist.

You assess RESEARCH EVIDENCE QUALITY only.
Do NOT assign legal risk (clear / caution / high-risk).
Do NOT decide clearance approval.
Do NOT perform defamation analysis.

CURRENT RESEARCH RESULT (JSON in state):
{{{STATE_RESEARCH_RESULT}?}}

EVALUATE whether ALL of the following are true:
1. status is "success" (not tool_failure / insufficient_evidence), OR
   status is "insufficient_evidence"/"tool_failure" AND a second targeted
   search has already been attempted and still cannot improve (see notes).
2. finding is specific and grounded in the citations.
3. citations include real URLs that clearly support the finding.
4. confidence >= {MIN_EVIDENCE_CONFIDENCE} for a successful identification,
   OR confidence correctly reflects weak/failed evidence when status is not success.

IF evidence is sufficiently strong and relevant for a final research result:
- Call the exit_loop tool immediately.
- Do not output extra commentary after calling exit_loop.

IF evidence is weak, ambiguous, missing citations, or confidence is too low
AND another research pass could help:
- Do NOT call exit_loop.
- Output a short, actionable refinement request (what to search next,
  what is missing). This text becomes feedback for the research agent.

IF status is tool_failure or insufficient_evidence and further searching is
unlikely to help (e.g. Parallel already failed, or the name is too generic
with no identifying context):
- Call exit_loop so the pipeline can return the honest failure/insufficient result.
""",
    tools=[exit_loop],
    output_key=STATE_RECHECK_FEEDBACK,
)


# LoopAgent is deprecated in google-adk 2.6.x in favor of Workflow, but remains
# the correct API matching the Business Specialist confidence re-check pattern.
character_name_specialist = LoopAgent(
    name="character_name_specialist",
    description=(
        "Character Name Research Specialist: Parallel MCP research + "
        "confidence re-check loop for one character_name Entity."
    ),
    sub_agents=[
        character_research_agent,
        character_confidence_recheck_agent,
    ],
    max_iterations=2,
)

# ADK convention alias when loading the agent package interactively.
root_agent = character_name_specialist
