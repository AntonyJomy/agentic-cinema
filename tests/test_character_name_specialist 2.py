"""
tests/test_character_name_specialist.py

Minimal local end-to-end test for the Character Name Research Specialist.

Uses a real character_name Entity (Elon Musk) and performs a REAL Parallel
MCP search (no mocks). Verifies:
  - research finding
  - research confidence
  - citations from Parallel
  - confidence re-check (exit_loop and/or loop agents ran)

Mirrors tests/test_business_specialist.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

# Mirror character_name_specialist key bridging for the runner process.
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from agents.character_name_specialist import (  # noqa: E402
    STATE_RECHECK_FEEDBACK,
    STATE_RESEARCH_RESULT,
    character_name_specialist,
)
from schemas.entities import Entity, EntityType, ScriptLocation  # noqa: E402
from schemas.research_result import ResearchResult, ResearchStatus  # noqa: E402

APP_NAME = "character_name_specialist_test"
USER_ID = "test_user"


def require_api_keys() -> None:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print(
            "Error: GOOGLE_API_KEY or GEMINI_API_KEY required in .env",
            file=sys.stderr,
        )
        sys.exit(1)


def build_elon_musk_entity() -> Entity:
    return Entity(
        name="Elon Musk",
        entity_type=EntityType.CHARACTER_NAME,
        context="The villain meets Elon Musk at the event.",
        location=ScriptLocation(
            page_number=5,
            scene_number=4,
            line_excerpt="The villain meets Elon Musk at the event.",
        ),
        confidence=0.95,
    )


def _part_text(part) -> str | None:
    return getattr(part, "text", None)


def _function_call(part):
    return getattr(part, "function_call", None)


def _function_response(part):
    return getattr(part, "function_response", None)


async def run_character_name_specialist(entity: Entity) -> dict:
    runner = InMemoryRunner(app_name=APP_NAME, agent=character_name_specialist)
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    prompt = (
        "Research the following screenplay Entity. "
        "entity_type must be treated as character_name.\n\n"
        f"{entity.model_dump_json(indent=2)}"
    )
    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    saw_parallel_tool_call = False
    saw_parallel_tool_response = False
    saw_exit_loop = False
    agents_seen: set[str] = set()
    research_payloads: list[str] = []

    print("=" * 72)
    print(f"ENTITY: {entity.name} ({entity.entity_type.value})")
    print("=" * 72)

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=user_message,
    ):
        if getattr(event, "author", None):
            agents_seen.add(event.author)

        if not event.content or not event.content.parts:
            continue

        for part in event.content.parts:
            fn_call = _function_call(part)
            if fn_call:
                name = fn_call.name or ""
                if name in {"web_search", "web_fetch"}:
                    saw_parallel_tool_call = True
                    print("\n[TOOL CALL — ADK → Parallel MCP]")
                    print(f"  name: {name}")
                    args = getattr(fn_call, "args", None)
                    if args:
                        print(f"  args: {args}")
                if name == "exit_loop":
                    saw_exit_loop = True
                    print("\n[CONFIDENCE RE-CHECK] exit_loop called — evidence accepted")

            fn_resp = _function_response(part)
            if fn_resp:
                name = fn_resp.name or ""
                if name in {"web_search", "web_fetch"}:
                    saw_parallel_tool_response = True
                    print("\n[TOOL RESPONSE — Parallel MCP → ADK]")
                    print(f"  name: {name}")
                    preview = str(getattr(fn_resp, "response", None))
                    if len(preview) > 1200:
                        preview = preview[:1200] + "...(truncated)"
                    print(f"  response: {preview}")

            text = _part_text(part)
            if text and event.author == "character_research_agent":
                research_payloads.append(text)

    # Prefer structured result from session state (output_key).
    refreshed = await runner.session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session.id,
    )
    state = refreshed.state if refreshed else {}
    raw_result = state.get(STATE_RESEARCH_RESULT)
    recheck_feedback = state.get(STATE_RECHECK_FEEDBACK)

    if raw_result is None and research_payloads:
        raw_result = research_payloads[-1]

    if isinstance(raw_result, str):
        try:
            raw_result = json.loads(raw_result)
        except json.JSONDecodeError:
            pass

    return {
        "raw_result": raw_result,
        "recheck_feedback": recheck_feedback,
        "saw_parallel_tool_call": saw_parallel_tool_call,
        "saw_parallel_tool_response": saw_parallel_tool_response,
        "saw_exit_loop": saw_exit_loop,
        "agents_seen": agents_seen,
    }


def main() -> int:
    require_api_keys()
    entity = build_elon_musk_entity()
    outcome = asyncio.run(run_character_name_specialist(entity))

    print("\n" + "=" * 72)
    print("FINAL RESEARCH RESULT")
    print("=" * 72)

    raw = outcome["raw_result"]
    if raw is None:
        print("FAILED: No research result in session state or agent output.")
        return 1

    try:
        result = ResearchResult.model_validate(raw)
    except Exception as exc:
        print(f"FAILED: ResearchResult validation error: {exc}")
        print(f"Raw: {raw}")
        return 1

    print(result.model_dump_json(indent=2))

    print("\n" + "=" * 72)
    print("VERIFICATION")
    print("=" * 72)
    print(f"entity_name:                 {result.entity_name}")
    print(f"entity_type:                 {result.entity_type}")
    print(f"finding:                     {result.finding}")
    print(f"confidence (research):       {result.confidence}")
    print(f"status:                      {result.status}")
    print(f"citations count:             {len(result.citations)}")
    for i, cite in enumerate(result.citations, start=1):
        print(f"  [{i}] {cite.source_url}")
        print(f"      {cite.summary}")

    print(f"Parallel MCP tool called:    {'YES' if outcome['saw_parallel_tool_call'] else 'NO'}")
    print(
        f"Parallel MCP tool response:  "
        f"{'YES' if outcome['saw_parallel_tool_response'] else 'NO'}"
    )
    print(f"exit_loop (re-check pass):   {'YES' if outcome['saw_exit_loop'] else 'NO'}")
    print(f"agents seen:                 {sorted(outcome['agents_seen'])}")
    if outcome["recheck_feedback"]:
        print(f"recheck feedback (state):    {outcome['recheck_feedback']}")

    recheck_ran = (
        outcome["saw_exit_loop"]
        or "character_confidence_recheck_agent" in outcome["agents_seen"]
        or outcome["recheck_feedback"] is not None
    )
    print(f"confidence re-check ran:     {'YES' if recheck_ran else 'NO'}")

    ok = True
    if result.entity_name != "Elon Musk":
        print("FAILED: entity_name should be Elon Musk (from Entity)")
        ok = False
    if result.entity_type != EntityType.CHARACTER_NAME:
        print("FAILED: entity_type should be character_name")
        ok = False
    if not outcome["saw_parallel_tool_call"] or not outcome["saw_parallel_tool_response"]:
        print("FAILED: Expected a real Parallel MCP web_search/web_fetch round-trip")
        ok = False
    if not recheck_ran:
        print("FAILED: Confidence re-check did not execute")
        ok = False
    if result.status == ResearchStatus.SUCCESS and not result.citations:
        print("FAILED: Successful research must include citations")
        ok = False
    if result.status == ResearchStatus.TOOL_FAILURE:
        print("FAILED: Parallel MCP tool failure — ticket not complete")
        ok = False

    print("\n" + "=" * 72)
    print("ALL TESTS PASSED" if ok else "TESTS FAILED")
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
