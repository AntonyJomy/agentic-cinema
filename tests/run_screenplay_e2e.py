#!/usr/bin/env python3
"""
End-to-end demo: test_screenplay.txt → Extraction → available specialists.

Shows each available agent's reply. Downstream agents not yet implemented
(scoring / legal / gatekeeper) are listed as skipped.
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
    STATE_RESEARCH_RESULT as BUSINESS_STATE_RESULT,
    business_specialist,
)
from agents.character_name_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as CHARACTER_STATE_RESULT,
    character_name_specialist,
)
from agents.extraction_agent import extractor  # noqa: E402
from agents.music_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as MUSIC_STATE_RESULT,
    music_specialist,
)
from agents.trademark_brand_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as TRADEMARK_STATE_RESULT,
    trademark_brand_specialist,
)
from agents.address_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as ADDRESS_STATE_RESULT,
    address_specialist,
)
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


async def run_specialist(
    *,
    agent,
    state_key: str,
    research_agent_name: str,
    entity_type_label: str,
    title: str,
    entity: Entity,
    index: int,
    total: int,
) -> ResearchResult | None:
    banner(f"{title} ({index}/{total}): {entity.name}")
    print("Input Entity:")
    print(entity.model_dump_json(indent=2))

    app_name = f"e2e_{entity_type_label}_{index}"
    runner = InMemoryRunner(app_name=app_name, agent=agent)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=USER_ID,
    )

    prompt = (
        f"Research the following screenplay Entity. "
        f"entity_type must be treated as {entity_type_label}.\n\n"
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
            if text and getattr(event, "author", None) == research_agent_name:
                research_texts.append(text)

    refreshed = await runner.session_service.get_session(
        app_name=app_name,
        user_id=USER_ID,
        session_id=session.id,
    )
    raw = (refreshed.state or {}).get(state_key) if refreshed else None
    if raw is None and research_texts:
        raw = research_texts[-1]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            pass

    if raw is None:
        print(f"\n--- {title} reply: NONE ---")
        return None

    result = ResearchResult.model_validate(raw)
    print(f"\n--- {title} reply ---")
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
    characters = [
        e for e in entities.entities if e.entity_type == EntityType.CHARACTER_NAME
    ]
    songs = [e for e in entities.entities if e.entity_type == EntityType.SONG]
    brands = [e for e in entities.entities if e.entity_type == EntityType.LOGO_BRAND]
    addresses = [e for e in entities.entities if e.entity_type == EntityType.ADDRESS]

    banner("ROUTING")
    print(f"Business entities → Business Specialist: {len(businesses)}")
    for e in businesses:
        print(f"  - {e.name}")
    print(f"Character name entities → Character Name Specialist: {len(characters)}")
    for e in characters:
        print(f"  - {e.name}")
    print(f"Song entities → Music Specialist: {len(songs)}")
    for e in songs:
        print(f"  - {e.name}")
    print(f"Logo/brand entities → Trademark/Brand Specialist: {len(brands)}")
    for e in brands:
        print(f"  - {e.name}")
    print(f"Address entities → Address Specialist: {len(addresses)}")
    for e in addresses:
        print(f"  - {e.name}")

    handled_types = {
        EntityType.BUSINESS,
        EntityType.CHARACTER_NAME,
        EntityType.SONG,
        EntityType.LOGO_BRAND,
        EntityType.ADDRESS,
    }
    other = [e for e in entities.entities if e.entity_type not in handled_types]
    if other:
        print("\nNot yet implemented (skipped):")
        for e in other:
            print(f"  - {e.name!r} ({e.entity_type.value}) → specialist TBD")

    business_results: list[ResearchResult] = []
    for i, entity in enumerate(businesses, start=1):
        result = await run_specialist(
            agent=business_specialist,
            state_key=BUSINESS_STATE_RESULT,
            research_agent_name="business_research_agent",
            entity_type_label="business",
            title="AGENT 2 — BUSINESS SPECIALIST",
            entity=entity,
            index=i,
            total=len(businesses),
        )
        if result:
            business_results.append(result)

    character_results: list[ResearchResult] = []
    for i, entity in enumerate(characters, start=1):
        result = await run_specialist(
            agent=character_name_specialist,
            state_key=CHARACTER_STATE_RESULT,
            research_agent_name="character_research_agent",
            entity_type_label="character_name",
            title="AGENT 3 — CHARACTER NAME SPECIALIST",
            entity=entity,
            index=i,
            total=len(characters),
        )
        if result:
            character_results.append(result)

    if not characters:
        banner("AGENT 3 — CHARACTER NAME SPECIALIST")
        print(
            "No entity_type=character_name found in this screenplay extraction.\n"
            "Nothing to research with the Character Name Specialist."
        )

    music_results: list[ResearchResult] = []
    for i, entity in enumerate(songs, start=1):
        result = await run_specialist(
            agent=music_specialist,
            state_key=MUSIC_STATE_RESULT,
            research_agent_name="music_research_agent",
            entity_type_label="song",
            title="AGENT 4 — MUSIC SPECIALIST",
            entity=entity,
            index=i,
            total=len(songs),
        )
        if result:
            music_results.append(result)

    if not songs:
        banner("AGENT 4 — MUSIC SPECIALIST")
        print(
            "No entity_type=song found in this screenplay extraction.\n"
            "Nothing to research with the Music Specialist."
        )

    brand_results: list[ResearchResult] = []
    for i, entity in enumerate(brands, start=1):
        result = await run_specialist(
            agent=trademark_brand_specialist,
            state_key=TRADEMARK_STATE_RESULT,
            research_agent_name="trademark_brand_research_agent",
            entity_type_label="logo_brand",
            title="AGENT 5 — TRADEMARK/BRAND SPECIALIST",
            entity=entity,
            index=i,
            total=len(brands),
        )
        if result:
            brand_results.append(result)

    if not brands:
        banner("AGENT 5 — TRADEMARK/BRAND SPECIALIST")
        print(
            "No entity_type=logo_brand found in this screenplay extraction.\n"
            "Nothing to research with the Trademark/Brand Specialist."
        )

    address_results: list[ResearchResult] = []
    for i, entity in enumerate(addresses, start=1):
        result = await run_specialist(
            agent=address_specialist,
            state_key=ADDRESS_STATE_RESULT,
            research_agent_name="address_research_agent",
            entity_type_label="address",
            title="AGENT 6 — ADDRESS SPECIALIST",
            entity=entity,
            index=i,
            total=len(addresses),
        )
        if result:
            address_results.append(result)

    if not addresses:
        banner("AGENT 6 — ADDRESS SPECIALIST")
        print(
            "No entity_type=address found in this screenplay extraction.\n"
            "Nothing to research with the Address Specialist."
        )

    banner("END-TO-END SUMMARY")
    print(f"Extraction entities:              {entities.entity_count}")
    print(f"Business researched:              {len(business_results)}/{len(businesses)}")
    for r in business_results:
        print(
            f"  • {r.entity_name}: status={r.status.value} "
            f"confidence={r.confidence:.2f} citations={len(r.citations)}"
        )
        print(f"    finding: {r.finding[:160]}{'...' if len(r.finding) > 160 else ''}")

    print(
        f"Character names researched:       "
        f"{len(character_results)}/{len(characters)}"
    )
    for r in character_results:
        print(
            f"  • {r.entity_name}: status={r.status.value} "
            f"confidence={r.confidence:.2f} citations={len(r.citations)}"
        )
        print(f"    finding: {r.finding[:160]}{'...' if len(r.finding) > 160 else ''}")

    print(f"Songs researched:                 {len(music_results)}/{len(songs)}")
    for r in music_results:
        print(
            f"  • {r.entity_name}: status={r.status.value} "
            f"confidence={r.confidence:.2f} citations={len(r.citations)}"
        )
        print(f"    finding: {r.finding[:160]}{'...' if len(r.finding) > 160 else ''}")

    print(f"Brands researched:                {len(brand_results)}/{len(brands)}")
    for r in brand_results:
        print(
            f"  • {r.entity_name}: status={r.status.value} "
            f"confidence={r.confidence:.2f} citations={len(r.citations)}"
        )
        print(f"    finding: {r.finding[:160]}{'...' if len(r.finding) > 160 else ''}")

    print(f"Addresses researched:             {len(address_results)}/{len(addresses)}")
    for r in address_results:
        print(
            f"  • {r.entity_name}: status={r.status.value} "
            f"confidence={r.confidence:.2f} citations={len(r.citations)}"
        )
        print(f"    finding: {r.finding[:160]}{'...' if len(r.finding) > 160 else ''}")

    print("\nDownstream agents not run (out of scope / not built yet):")
    print("  - Risk Scoring Agent")
    print("  - Legal Review")
    print("  - Gatekeeper clearance decision")
    print("  - Final Clearance Report")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
