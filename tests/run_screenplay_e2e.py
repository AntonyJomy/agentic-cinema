#!/usr/bin/env python3
"""
End-to-end: test_screenplay.txt → Extraction → ALL research specialists.

Every implemented specialist is exercised. If extraction misses an entity type,
a fallback test entity is used so all 6 specialists still run.

Verifies: Parallel MCP, citations, confidence re-check, ResearchResult schema.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
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

from agents.address_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as ADDRESS_STATE_RESULT,
    address_specialist,
)
from agents.business_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as BUSINESS_STATE_RESULT,
    business_specialist,
)
from agents.character_name_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as CHARACTER_STATE_RESULT,
    character_name_specialist,
)
from agents.extraction_agent import extractor  # noqa: E402
from agents.literary_reference_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as LITERARY_STATE_RESULT,
    literary_reference_specialist,
)
from agents.music_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as MUSIC_STATE_RESULT,
    music_specialist,
)
from agents.trademark_brand_specialist import (  # noqa: E402
    STATE_RESEARCH_RESULT as TRADEMARK_STATE_RESULT,
    trademark_brand_specialist,
)
from schemas.entities import Entities, Entity, EntityType, ScriptLocation  # noqa: E402
from schemas.research_result import ResearchResult, ResearchStatus  # noqa: E402

SCREENPLAY_PATH = project_root / "tests" / "scripts" / "test_screenplay.txt"
USER_ID = "e2e-user"


@dataclass
class SpecialistConfig:
    entity_type: EntityType
    agent: object
    state_key: str
    research_agent_name: str
    title: str
    agent_number: int


@dataclass
class RunOutcome:
    entity: Entity
    result: ResearchResult | None
    source: str  # "extracted" | "fallback"
    saw_parallel: bool = False
    saw_exit_loop: bool = False


SPECIALISTS: list[SpecialistConfig] = [
    SpecialistConfig(
        EntityType.BUSINESS, business_specialist, BUSINESS_STATE_RESULT,
        "business_research_agent", "BUSINESS SPECIALIST", 2,
    ),
    SpecialistConfig(
        EntityType.CHARACTER_NAME, character_name_specialist, CHARACTER_STATE_RESULT,
        "character_research_agent", "CHARACTER NAME SPECIALIST", 3,
    ),
    SpecialistConfig(
        EntityType.SONG, music_specialist, MUSIC_STATE_RESULT,
        "music_research_agent", "MUSIC SPECIALIST", 4,
    ),
    SpecialistConfig(
        EntityType.LOGO_BRAND, trademark_brand_specialist, TRADEMARK_STATE_RESULT,
        "trademark_brand_research_agent", "TRADEMARK/BRAND SPECIALIST", 5,
    ),
    SpecialistConfig(
        EntityType.ADDRESS, address_specialist, ADDRESS_STATE_RESULT,
        "address_research_agent", "ADDRESS SPECIALIST", 6,
    ),
    SpecialistConfig(
        EntityType.QUOTE_OR_LITERARY_REFERENCE,
        literary_reference_specialist, LITERARY_STATE_RESULT,
        "literary_reference_research_agent", "LITERARY REFERENCE SPECIALIST", 7,
    ),
]

FALLBACK_ENTITIES: dict[EntityType, Entity] = {
    EntityType.BUSINESS: Entity(
        name="McDonald's", entity_type=EntityType.BUSINESS,
        context="John walks into McDonald's and orders a coffee.",
        location=ScriptLocation(page_number=4, scene_number=3,
                                line_excerpt="John walks into McDonald's."),
        confidence=0.96,
    ),
    EntityType.CHARACTER_NAME: Entity(
        name="Elon Musk", entity_type=EntityType.CHARACTER_NAME,
        context="The villain meets Elon Musk at the event.",
        location=ScriptLocation(page_number=5, scene_number=4,
                                line_excerpt="The villain meets Elon Musk at the event."),
        confidence=0.95,
    ),
    EntityType.SONG: Entity(
        name="Love Story", entity_type=EntityType.SONG,
        context="Sarah listens to Love Story while driving.",
        location=ScriptLocation(page_number=7, scene_number=5,
                                line_excerpt="Sarah starts singing Love Story."),
        confidence=0.95,
    ),
    EntityType.LOGO_BRAND: Entity(
        name="Coca-Cola", entity_type=EntityType.LOGO_BRAND,
        context="A red truck with the Coca-Cola logo drives past.",
        location=ScriptLocation(page_number=3, scene_number=2,
                                line_excerpt="the Coca-Cola logo clearly visible."),
        confidence=0.97,
    ),
    EntityType.ADDRESS: Entity(
        name="1600 Amphitheatre Parkway, Mountain View, California",
        entity_type=EntityType.ADDRESS,
        context='A SIGN reads "1600 Amphitheatre Parkway, Mountain View, California".',
        location=ScriptLocation(page_number=2, scene_number=1,
                                line_excerpt='A SIGN reads "1600 Amphitheatre Parkway, Mountain View, California".'),
        confidence=0.98,
    ),
    EntityType.QUOTE_OR_LITERARY_REFERENCE: Entity(
        name="To be, or not to be, that is the question",
        entity_type=EntityType.QUOTE_OR_LITERARY_REFERENCE,
        context="The actor recites: To be, or not to be, that is the question.",
        location=ScriptLocation(page_number=9, scene_number=6,
                                line_excerpt='"To be, or not to be, that is the question."'),
        confidence=0.96,
    ),
}

UNIMPLEMENTED = {
    EntityType.PHONE_NUMBER,
    EntityType.LICENSE_PLATE,
    EntityType.REAL_PUBLIC_FIGURE,
}


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


async def run_extraction(screenplay_text: str) -> Entities:
    banner("AGENT 1 — EXTRACTION")
    session_service = InMemorySessionService()
    runner = Runner(agent=extractor, app_name="e2e_extraction",
                    session_service=session_service)
    await session_service.create_session(
        app_name="e2e_extraction", user_id=USER_ID, session_id="extraction")

    final_text = None
    async for event in runner.run_async(
        user_id=USER_ID, session_id="extraction",
        new_message=types.Content(role="user", parts=[types.Part(text=screenplay_text)]),
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


def build_workload(entities: Entities) -> dict[EntityType, list[tuple[Entity, str]]]:
    """All extracted entities per type + fallback if extraction found none."""
    by_type: dict[EntityType, list[tuple[Entity, str]]] = {
        cfg.entity_type: [] for cfg in SPECIALISTS
    }
    for entity in entities.entities:
        if entity.entity_type in by_type:
            by_type[entity.entity_type].append((entity, "extracted"))
    for cfg in SPECIALISTS:
        if not by_type[cfg.entity_type]:
            by_type[cfg.entity_type].append((FALLBACK_ENTITIES[cfg.entity_type], "fallback"))
    return by_type


async def run_specialist(
    config: SpecialistConfig, entity: Entity, source: str, index: int, total: int,
) -> RunOutcome:
    outcome = RunOutcome(entity=entity, result=None, source=source)
    banner(f"AGENT {config.agent_number} — {config.title} ({index}/{total}): {entity.name}")
    if source == "fallback":
        print(f"NOTE: Fallback entity — extraction found no {config.entity_type.value}.")
    print("Input Entity:")
    print(entity.model_dump_json(indent=2))

    app_name = f"e2e_{config.entity_type.value}_{index}"
    runner = InMemoryRunner(app_name=app_name, agent=config.agent)
    session = await runner.session_service.create_session(app_name=app_name, user_id=USER_ID)

    prompt = (
        f"Research the following screenplay Entity. "
        f"entity_type must be treated as {config.entity_type.value}.\n\n"
        f"{entity.model_dump_json(indent=2)}"
    )
    research_texts: list[str] = []

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
    ):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            fn_call = getattr(part, "function_call", None)
            if fn_call:
                name = fn_call.name or ""
                if name in {"web_search", "web_fetch"}:
                    outcome.saw_parallel = True
                    print(f"\n  [Parallel MCP] {name}")
                if name == "exit_loop":
                    outcome.saw_exit_loop = True
                    print("\n  [Confidence re-check] exit_loop")

            text = getattr(part, "text", None)
            if text and getattr(event, "author", None) == config.research_agent_name:
                research_texts.append(text)

    refreshed = await runner.session_service.get_session(
        app_name=app_name, user_id=USER_ID, session_id=session.id)
    raw = (refreshed.state or {}).get(config.state_key) if refreshed else None
    if raw is None and research_texts:
        raw = research_texts[-1]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            pass

    if raw is None:
        print(f"\n--- {config.title} reply: NONE ---")
        return outcome

    outcome.result = ResearchResult.model_validate(raw)
    print(f"\n--- {config.title} reply ---")
    print(outcome.result.model_dump_json(indent=2))
    print(f"\nParallel MCP: {outcome.saw_parallel} | Re-check: {outcome.saw_exit_loop}")
    return outcome


def validate(config: SpecialistConfig, outcome: RunOutcome) -> list[str]:
    errors: list[str] = []
    r = outcome.result
    if r is None:
        return ["No research result"]
    if r.entity_type != config.entity_type:
        errors.append(f"wrong entity_type: {r.entity_type.value}")
    if r.entity_name != outcome.entity.name:
        errors.append(f"wrong entity_name: {r.entity_name!r}")
    if not outcome.saw_parallel:
        errors.append("Parallel MCP not called")
    if not outcome.saw_exit_loop:
        errors.append("Confidence re-check (exit_loop) did not run")
    if r.status == ResearchStatus.TOOL_FAILURE:
        errors.append("tool_failure status")
    if r.status == ResearchStatus.SUCCESS and not r.citations:
        errors.append("success but no citations")
    return errors


async def main() -> int:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("Error: set GOOGLE_API_KEY or GEMINI_API_KEY in .env", file=sys.stderr)
        return 1

    screenplay_text = SCREENPLAY_PATH.read_text(encoding="utf-8")
    banner("SCREENPLAY")
    print(f"File: {SCREENPLAY_PATH} ({len(screenplay_text)} chars)")

    entities = await run_extraction(screenplay_text)
    workload = build_workload(entities)

    banner("ROUTING PLAN (all 6 specialists)")
    for cfg in SPECIALISTS:
        items = workload[cfg.entity_type]
        print(f"\nAgent {cfg.agent_number} — {cfg.title}:")
        for entity, src in items:
            print(f"  • [{src}] {entity.name}")

    skipped = [e for e in entities.entities if e.entity_type in UNIMPLEMENTED]
    if skipped:
        print("\nExtracted but no specialist yet:")
        for e in skipped:
            print(f"  • {e.name!r} ({e.entity_type.value})")

    all_outcomes: list[tuple[SpecialistConfig, RunOutcome]] = []
    for cfg in SPECIALISTS:
        for i, (entity, source) in enumerate(workload[cfg.entity_type], start=1):
            outcome = await run_specialist(cfg, entity, source, i, len(workload[cfg.entity_type]))
            all_outcomes.append((cfg, outcome))

    banner("VERIFICATION SUMMARY")
    passed = failed = 0
    specialists_run: set[int] = set()

    for cfg, outcome in all_outcomes:
        specialists_run.add(cfg.agent_number)
        errors = validate(cfg, outcome)
        ok = not errors
        passed += ok
        failed += not ok
        tag = "PASS" if ok else "FAIL"
        r = outcome.result
        if r:
            print(
                f"[{tag}] Agent {cfg.agent_number} {cfg.title} "
                f"({outcome.source}) {r.entity_name}: "
                f"status={r.status.value} conf={r.confidence:.2f} "
                f"cites={len(r.citations)} parallel={outcome.saw_parallel} "
                f"recheck={outcome.saw_exit_loop}"
            )
        else:
            print(f"[{tag}] Agent {cfg.agent_number} {cfg.title} ({outcome.source}): NO RESULT")
        for e in errors:
            print(f"       ✗ {e}")

    banner("COVERAGE")
    print(f"Agents checked:  1 (Extraction) + {len(specialists_run)} specialists = {1 + len(specialists_run)}")
    print(f"Expected:        7 (Extraction + 6 specialists)")
    print(f"Runs passed:     {passed}")
    print(f"Runs failed:     {failed}")
    print("\nNot built yet: Risk Scoring, Legal Review, Gatekeeper, Final Report")
    print("No specialist:   phone_number, license_plate, real_public_figure")

    banner("RESULT")
    if len(specialists_run) < 6:
        print(f"INCOMPLETE — only {len(specialists_run)}/6 specialists ran")
        return 1
    if failed:
        print(f"FAILED — {failed} run(s) failed verification")
        return 1
    print(f"PASSED — all 6 specialists verified ({passed} entity run(s))")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
