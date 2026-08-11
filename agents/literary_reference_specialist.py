"""
agents/literary_reference_specialist.py

Quote/Literary Reference Research Specialist for screenplay E&O clearance.

Receives ONE Entity with entity_type="quote_or_literary_reference", researches
whether it corresponds to a known published work using Parallel Search MCP,
and returns a ResearchResult (finding + research confidence + citations).

Wrapped in LoopAgent for a confidence re-check (max ~2 iterations).

Follows the same structure as agents/business_specialist.py.

This agent does NOT perform legal risk scoring (clear/caution/high-risk),
copyright clearance, or licence conclusions.
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
STATE_RESEARCH_RESULT = "literary_reference_research_result"
STATE_RECHECK_FEEDBACK = "literary_reference_confidence_recheck_feedback"

# Minimum research confidence that the re-check agent treats as "strong enough".
# This is research-evidence strength only — not a legal risk threshold.
MIN_EVIDENCE_CONFIDENCE = 0.75


literary_reference_research_agent = LlmAgent(
    model=MODEL,
    name="literary_reference_research_agent",
    description=(
        "Researches one quote_or_literary_reference Entity via Parallel Search "
        "MCP and produces a structured ResearchResult with citations."
    ),
    instruction=f"""
You are the Quote/Literary Reference Research Specialist in a screenplay E&O
clearance system.

OBJECTIVE:
Determine whether a quote or literary reference extracted from a screenplay
corresponds to a known published work and gather reliable web evidence about
its source, including where applicable:
- exact quote/source
- author
- book/poem/work
- publication
- original source
- official or authoritative references
- whether the reference corresponds to a known published work

You are a RESEARCH agent only. Do NOT assign legal risk labels
(clear / caution / high-risk). Do NOT make clearance decisions.
Do NOT state that something is legally cleared or requires a licence.
Do NOT make a final copyright/legal determination.

INPUT:
You receive exactly ONE Entity. It MUST have entity_type = "quote_or_literary_reference".
Use the Entity fields dynamically:
- name (the quote or literary reference text — never invent a different quote)
- context (screenplay usage; use this to disambiguate)
- location (page/scene/line_excerpt) when present
- confidence (extraction confidence — informational only; do not copy it as research confidence)

OPTIONAL PRIOR FEEDBACK (from the confidence re-check agent):
{{{STATE_RECHECK_FEEDBACK}?}}

If prior feedback is present and asks for a refined search, perform a more
targeted Parallel search addressing those gaps. Otherwise run a fresh search.

PROCESS:
1. Read the Entity. Confirm entity_type is quote_or_literary_reference.
2. Build a research objective from the name and, only if available and useful,
   screenplay context.
   Example: "Determine whether 'To be, or not to be' is a real literary quote.
   Identify the author, work, and provide credible sources supporting the finding."
3. You MUST call the Parallel MCP web_search tool before answering.
   Prefer authoritative sources (original texts, scholarly references, reputable
   literary databases). Use web_fetch only if needed.
4. Do NOT rely on model memory for verification. Do NOT fabricate URLs or citations.
5. Produce a ResearchResult:
   - entity_name: from the Entity.name
   - entity_type: "quote_or_literary_reference"
   - entity_id: from the Entity if present
   - finding: concise statement of what the evidence supports (source attribution)
   - confidence: your confidence in the RESEARCH FINDING (0.0–1.0), NOT legal risk
   - citations: real URLs/summaries from Parallel tool results only
   - status:
       - "success" when credible evidence supports a clear finding
       - "insufficient_evidence" when evidence is weak/ambiguous/absent
       - "tool_failure" when Parallel MCP search fails or returns unusable errors
   - research_notes: brief note on search approach / remaining uncertainty / variants

FAILURE HANDLING:
- If Parallel fails: status=tool_failure, confidence low, finding states the tool/research failure, citations may be empty.
- If no credible evidence of a known published source: status=insufficient_evidence, say so explicitly, do not guess.
- If multiple possible sources exist, state the ambiguity with evidence and keep confidence appropriately calibrated.
""",
    tools=[build_parallel_mcp_toolset()],
    output_schema=ResearchResult,
    output_key=STATE_RESEARCH_RESULT,
)


literary_reference_confidence_recheck_agent = LlmAgent(
    model=MODEL,
    name="literary_reference_confidence_recheck_agent",
    description=(
        "Checks whether literary-reference research evidence is strong enough; "
        "exits the loop when sufficient, otherwise requests refined research."
    ),
    instruction=f"""
You are the Confidence Re-check Agent for the Quote/Literary Reference Research Specialist.

You assess RESEARCH EVIDENCE QUALITY only.
Do NOT assign legal risk (clear / caution / high-risk).
Do NOT decide clearance approval.
Do NOT conclude copyright status or whether a licence is required.

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
unlikely to help (e.g. Parallel already failed, or the quote is too generic):
- Call exit_loop so the pipeline can return the honest failure/insufficient result.
""",
    tools=[exit_loop],
    output_key=STATE_RECHECK_FEEDBACK,
)


# LoopAgent is deprecated in google-adk 2.6.x in favor of Workflow, but remains
# the correct API matching the Business Specialist confidence re-check pattern.
literary_reference_specialist = LoopAgent(
    name="literary_reference_specialist",
    description=(
        "Quote/Literary Reference Research Specialist: Parallel MCP research + "
        "confidence re-check loop for one quote_or_literary_reference Entity."
    ),
    sub_agents=[
        literary_reference_research_agent,
        literary_reference_confidence_recheck_agent,
    ],
    max_iterations=2,
)

# ADK convention alias when loading the agent package interactively.
root_agent = literary_reference_specialist
