#!/usr/bin/env python3
"""
End-to-end demo: test_screenplay.txt → Extraction → Business Specialist(s).

Shows each available agent's reply. Specialists not yet implemented
(character / music / scoring / legal / gatekeeper) are listed as skipped.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from agents.business_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT,
    business_specialist,
)
from agents.extraction_agent import extractor  # noqa: E402
from schemas.entities import Entities, Entity, EntityType  # noqa: E402
from schemas.research_result import ResearchResult  # noqa: E402

SCREENPLAY_PATH = project_root / "tests" / "scripts" / "test_screenplay.txt"
USER_ID = "e2e-user"


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def run_extraction(screenplay_text: str) -> Entities:
    banner("AGENT 1 — EXTRACTION")
    session_service = InMemorySessionService()
    runner = Runner(
        agent=extractor,
        app_name="e2e_extraction",
        session_service=session_service,
    )
    await session_service.create_session(
        app_name="e2e_extraction",
        user_id=USER_ID,
        session_id="extraction",
    )

    final_text = None
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id="extraction",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=screenplay_text)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    if not final_text:
        raise RuntimeError("Extraction agent returned no final response")

    print("\n--- Raw extraction reply ---\n")
    print(final_text)

    parsed = json.loads(final_text)
    parsed["metadata"] = {
        "model_used": "gemini-3.6-flash",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "extraction_agent_version": "0.1.0",
        "total_pages_scanned": parsed.get("metadata", {}).get("total_pages_scanned"),
    }
    entities = Entities.model_validate(parsed)

    print(f"\nExtracted {entities.entity_count} entities:\n")
    for i, e in enumerate(entities.entities, start=1):
        print(
            f"  [{i}] {e.name!r:30} type={e.entity_type.value:28} "
            f"risk={e.risk_category.value if e.risk_category else None} "
            f"conf={e.confidence:.2f}"
        )
    return entities


async def run_business_specialist(entity: Entity, index: int, total: int) -> ResearchResult | None:
    banner(
        f"AGENT 2 — BUSINESS SPECIALIST ({index}/{total}): {entity.name}"
    )
    print("Input Entity:")
    print(entity.model_dump_json(indent=2))

    runner = InMemoryRunner(app_name="e2e_business", agent=business_specialist)
    session = await runner.session_service.create_session(
        app_name="e2e_business",
        user_id=USER_ID,
    )

    prompt = (
        "Research the following screenplay Entity. "
        "entity_type must be treated as business.\n\n"
        f"{entity.model_dump_json(indent=2)}"
    )

    saw_parallel = False
    saw_exit_loop = False
    research_texts: list[str] = []

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call:
                name = fn_call.name or ""
                if name in {"web_search", "web_fetch"}:
                    saw_parallel = True
                    print(f"\n  [Parallel MCP] {name}({getattr(fn_call, 'args', {})})")
                if name == "exit_loop":
                    saw_exit_loop = True
                    print("\n  [Confidence re-check] exit_loop → evidence accepted")

            text = getattr(part, "text", None)
            if text and getattr(event, "author", None) == "business_research_agent":
                research_texts.append(text)

    refreshed = await runner.session_service.get_session(
        app_name="e2e_business",
        user_id=USER_ID,
        session_id=session.id,
    )
    raw = (refreshed.state or {}).get(STATE_RESEARCH_RESULT) if refreshed else None
    if raw is None and research_texts:
        raw = research_texts[-1]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            pass

    if raw is None:
        print("\n--- Business specialist reply: NONE ---")
        return None

    result = ResearchResult.model_validate(raw)
    print("\n--- Business specialist reply ---")
    print(result.model_dump_json(indent=2))
    print(f"\nParallel MCP used: {saw_parallel} | Re-check exit_loop: {saw_exit_loop}")
    return result


async def main() -> int:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("Error: set GOOGLE_API_KEY or GEMINI_API_KEY in .env", file=sys.stderr)
        return 1

    screenplay_text = SCREENPLAY_PATH.read_text(encoding="utf-8")
    banner("SCREENPLAY")
    print(f"File: {SCREENPLAY_PATH}")
    print(f"Length: {len(screenplay_text)} chars")
    print(screenplay_text)

    entities = await run_extraction(screenplay_text)

    businesses = [e for e in entities.entities if e.entity_type == EntityType.BUSINESS]
    banner("ROUTING")
    print(f"Business entities → Business Specialist: {len(businesses)}")
    for e in businesses:
        print(f"  - {e.name}")

    other = [e for e in entities.entities if e.entity_type != EntityType.BUSINESS]
    if other:
        print("\nNot yet implemented (skipped):")
        for e in other:
            print(f"  - {e.name!r} ({e.entity_type.value}) → specialist TBD")

    results: list[ResearchResult] = []
    for i, entity in enumerate(businesses, start=1):
        result = await run_business_specialist(entity, i, len(businesses))
        if result:
            results.append(result)

    banner("END-TO-END SUMMARY")
    print(f"Extraction entities:     {entities.entity_count}")
    print(f"Business researched:     {len(results)}/{len(businesses)}")
    for r in results:
        cites = len(r.citations)
        print(
            f"  • {r.entity_name}: status={r.status.value} "
            f"confidence={r.confidence:.2f} citations={cites}"
        )
        print(f"    finding: {r.finding[:160]}{'...' if len(r.finding) > 160 else ''}")

    print("\nDownstream agents not run (out of scope / not built yet):")
    print("  - Character Name Specialist")
    print("  - Music Specialist")
    print("  - Risk Scoring Agent")
    print("  - Legal Review")
    print("  - Gatekeeper clearance decision")
    print("  - Final Clearance Report")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
