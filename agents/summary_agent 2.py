"""
agents/summary_agent.py

Summary Agent for screenplay E&O clearance.

Receives completed RiskResult items for a clearance run and produces a
concise plain-language SummaryResult for the legal reviewer.

This agent does NOT perform web research, call Parallel, or change risk
classifications.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from schemas.risk_result import RiskLevel, RiskResult
from schemas.summary_result import SummaryResult

if TYPE_CHECKING:
    pass

load_dotenv()

if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

MODEL = "gemini-3.6-flash"


def compute_risk_counts(risk_results: list[RiskResult]) -> dict[str, int]:
    """Compute risk counts from supplied RiskResult items."""
    return {
        "total_entities": len(risk_results),
        "clear_count": sum(1 for r in risk_results if r.risk_level == RiskLevel.CLEAR),
        "caution_count": sum(1 for r in risk_results if r.risk_level == RiskLevel.CAUTION),
        "high_risk_count": sum(1 for r in risk_results if r.risk_level == RiskLevel.HIGH_RISK),
    }


def build_summary_prompt(
    risk_results: list[RiskResult],
    script_title: str | None = None,
) -> str:
    """Build the user message for the summary agent."""
    title = script_title or "Untitled Screenplay"
    results_json = json.dumps(
        [result.model_dump(mode="json") for result in risk_results],
        indent=2,
    )
    counts = compute_risk_counts(risk_results)
    return (
        "SUMMARY REQUEST\n\n"
        f"Produce a concise clearance overview for: {title}\n\n"
        "The following RiskResult items are complete and authoritative. "
        "Do NOT change any risk classifications.\n\n"
        f"## RISK RESULTS ({counts['total_entities']} entities)\n\n"
        f"{results_json}\n\n"
        "Return a SummaryResult with:\n"
        "- overall_summary: plain-language overview answering what was found, "
        "how many are clear/caution/high_risk, which items need legal attention, "
        "the most important reasons, and what evidence supports the findings\n"
        f"- total_entities: {counts['total_entities']}\n"
        f"- clear_count: {counts['clear_count']}\n"
        f"- caution_count: {counts['caution_count']}\n"
        f"- high_risk_count: {counts['high_risk_count']}\n"
        "- priority_items: bullet-style strings highlighting high-risk entities "
        "and other items requiring legal attention (use supplied reasoning only)"
    )


summarizer = LlmAgent(
    model=MODEL,
    name="summarizer",
    description=(
        "Summarises completed risk-scoring results into a plain-language "
        "clearance overview for legal review."
    ),
    instruction="""
You are the Summary Agent in a screenplay E&O clearance system.

OBJECTIVE
Produce a concise, plain-language overview of completed risk-scoring results
for a legal reviewer. Answer:
1. What was found?
2. How many items are clear?
3. How many require caution?
4. How many are high-risk?
5. Which items need legal attention?
6. What are the most important reasons?
7. What evidence supports those findings?

You are a SUMMARISATION agent only.

RULES (CRITICAL)
- Do NOT perform web research or call Parallel.
- Do NOT change risk classifications supplied in the input.
- Do NOT upgrade clear items or downgrade high_risk items.
- Do NOT invent classifications, citations, facts, or entities.
- Only summarise the supplied RiskResult evidence, reasoning, and citations.
- Preserve the exact risk level for each entity as provided.
- Use supplied triggered_rule and reasoning when explaining findings.
- Reference evidence only from the supplied citations.

OUTPUT
Return a SummaryResult with:
- overall_summary: 2-4 paragraphs, understandable without reading every result
- total_entities, clear_count, caution_count, high_risk_count: must match input
- priority_items: list of concise strings highlighting high_risk entities and
  items flagged requires_human_review=true; base each item on supplied reasoning

IMPORTANT
- High_risk entities MUST appear in priority_items.
- This is a summary for legal review, NOT a new legal conclusion.
- Do NOT use web search or external tools.
""",
    output_schema=SummaryResult,
)


def finalize_summary_result(
    risk_results: list[RiskResult],
    agent_output: SummaryResult,
) -> SummaryResult:
    """
    Merge agent narrative with authoritative counts from RiskResult items.

    Counts are computed programmatically to prevent LLM miscounts.
    """
    counts = compute_risk_counts(risk_results)
    return agent_output.model_copy(update=counts)


def collect_risk_results(entity_results: dict) -> list[RiskResult]:
    """Extract RiskResult items from orchestrator entity results."""
    risk_results: list[RiskResult] = []
    for results_list in entity_results.values():
        for result in results_list:
            if result.risk_result is not None:
                risk_results.append(result.risk_result)
    return risk_results
