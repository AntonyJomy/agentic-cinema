#!/usr/bin/env python3
"""
Orchestrator - Main pipeline for script clearance system.

This orchestrator runs the complete screenplay clearance workflow:
1. Extraction Agent: Reads screenplay text and identifies entities
2. Grounding Check: Validates entities against the screenplay (deterministic)
3. Routing: Sends grounded entities to appropriate specialist agents
4. Specialist Processing: Each entity is researched by its specialist
5. Risk Scoring Agent: Applies rubric to entity + research findings
6. Summary Agent: Produces plain-language clearance overview
7. Legal Review: Presents findings for explicit human decisions
8. Results Collection: Compiles scored findings, summary, and review package
9. Gatekeeper: Enforces clearance policy before final report
10. Output: Generates final clearance report (only if gatekeeper clears)

Usage:
    python orchestrator.py <screenplay_file.txt>
    python orchestrator.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Union

from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load environment variables
load_dotenv()
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# Import all agents
from agents.address_specialist import (
    STATE_RESEARCH_RESULT as ADDRESS_STATE_RESULT,
    address_specialist,
)
from agents.business_specialist import (
    STATE_RESEARCH_RESULT as BUSINESS_STATE_RESULT,
    build_business_specialist,
    business_specialist,
)
from agents.character_name_specialist import (
    STATE_RESEARCH_RESULT as CHARACTER_STATE_RESULT,
    character_name_specialist,
)
from agents.extraction_agent import extractor
from agents.model_config import get_gemini_model
from gatekeeper.deterministic_grounding import ground_entities
from agents.literary_reference_specialist import (
    STATE_RESEARCH_RESULT as LITERARY_STATE_RESULT,
    literary_reference_specialist,
)
from agents.music_specialist import (
    STATE_RESEARCH_RESULT as MUSIC_STATE_RESULT,
    music_specialist,
)
from agents.risk_scoring_agent import (
    build_scoring_prompt,
    finalize_risk_result,
    risk_scorer,
)
from agents.summary_agent import (
    build_summary_prompt,
    collect_risk_results,
    finalize_summary_result,
    summarizer,
)

from agents.trademark_brand_specialist import (
    STATE_RESEARCH_RESULT as TRADEMARK_STATE_RESULT,
    trademark_brand_specialist,
)

from schemas.entities import Entities, Entity, EntityType, ScriptLocation
from schemas.research_result import ResearchResult, ResearchStatus
from research.cache import (
    adapt_research_for_entity,
    entity_cache_key,
    is_cacheable_research,
    research_cache_enabled,
)
from research.retrieval import (
    build_rag_prompt_context,
    index_research_result,
    retrieve_similar_research,
)
from research.metrics import ResearchMetrics, ResearchSource, get_research_metrics
from research.rag_llm import synthesize_rag_result
from research.store import get_research_cache
from schemas.risk_result import RiskLevel, RiskResult
from schemas.summary_result import SummaryResult
from schemas.legal_review import LegalReviewPackage
from schemas.gatekeeper_result import GatekeeperResult, GatekeeperStatus
from legal_review.review_workflow import (
    build_legal_review_package,
    get_pending_required_reviews,
)
from gatekeeper.clearance_gate import evaluate_clearance


@dataclass
class SpecialistConfig:
    """Configuration for a specialist agent."""
    entity_type: EntityType
    agent: object
    state_key: str
    agent_name: str
    display_name: str
    agent_factory: Optional[Callable[[], object]] = None

    def create_agent(self) -> object:
        """Return a specialist agent instance for one entity research run."""
        if self.agent_factory is not None:
            return self.agent_factory()
        return self.agent


@dataclass
class EntityResult:
    """Result of processing a single entity."""
    entity: Entity
    research_result: Optional[ResearchResult]
    specialist_config: SpecialistConfig
    processing_time: float
    success: bool
    error: Optional[str] = None
    risk_result: Optional[RiskResult] = None
    research_source: str | None = None


@dataclass
class PipelineResult:
    """Complete pipeline results."""
    screenplay_path: str
    extracted_entities: Entities
    entity_results: Dict[EntityType, List[EntityResult]]
    start_time: datetime
    end_time: datetime
    total_entities: int
    successful_researches: int
    failed_researches: int
    
    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class ClearancePipelineResult:
    """Structured output from a full clearance pipeline run."""

    screenplay_path: str
    screenplay_text: str
    extracted_entities: Entities
    grounded_entities: Entities
    entity_results: Dict[EntityType, List[EntityResult]]
    summary_result: SummaryResult
    legal_review: LegalReviewPackage
    gatekeeper_result: GatekeeperResult
    report: Dict
    start_time: datetime
    end_time: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


ProgressCallback = Callable[["PipelineProgressEvent"], Union[None, Awaitable[None]]]


def _is_transient_gemini_error(exc: BaseException) -> bool:
    """True when Gemini/API is temporarily overloaded or rate-limited."""
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "503",
            "unavailable",
            "high demand",
            "429",
            "resource_exhausted",
            "resource exhausted",
            "try again later",
        )
    )


async def _retry_on_transient(
    operation,
    *,
    label: str,
    attempts: int = 4,
    base_delay: float = 2.0,
):
    """Retry an async callable on transient Gemini 503/429 errors."""
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_exc = exc
            if not _is_transient_gemini_error(exc) or attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(
                f"  ⚠️  {label}: transient Gemini error "
                f"(attempt {attempt}/{attempts}), retrying in {delay:.0f}s…"
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


@dataclass
class PipelineProgressEvent:
    """Real-time pipeline progress event for streaming UIs."""

    event: str
    agent_id: str
    agent_name: str
    phase: str
    status: str = "running"
    duration_seconds: float | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    output: dict | None = None
    message: str | None = None

    def to_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


async def _emit_progress(
    on_progress: ProgressCallback | None,
    progress_event: PipelineProgressEvent,
) -> None:
    if not on_progress:
        return
    result = on_progress(progress_event)
    if asyncio.iscoroutine(result):
        await result


def _extraction_output(entities: Entities) -> dict:
    return {
        "entity_count": entities.entity_count,
    }


def _grounding_output(
    *,
    extracted_count: int,
    grounded: List[Entity],
    rejected: List[Entity],
) -> dict:
    return {
        "extracted_count": extracted_count,
        "grounded_count": len(grounded),
        "rejected_count": len(rejected),
    }


def _specialist_output(entity_result: EntityResult) -> dict:
    research = entity_result.research_result
    output = {
        "success": entity_result.success,
        "citation_count": len(research.citations) if research else 0,
    }
    if entity_result.research_source:
        output["research_source"] = entity_result.research_source
    return output


def _risk_scoring_output(risk_result: RiskResult) -> dict:
    return {
        "requires_human_review": risk_result.requires_human_review,
    }


def _summary_output(summary: SummaryResult) -> dict:
    return {
        "total_entities": summary.total_entities,
    }


def _legal_review_output(package: LegalReviewPackage) -> dict:
    return {
        "pending_review_count": package.pending_review_count,
        "unresolved_required_count": package.unresolved_required_count,
    }


def _gatekeeper_output(result: GatekeeperResult) -> dict:
    return {
        "cleared_for_export": result.cleared_for_export,
    }


# Specialist configurations
SPECIALISTS: List[SpecialistConfig] = [
    SpecialistConfig(
        entity_type=EntityType.BUSINESS,
        agent=business_specialist,
        agent_factory=build_business_specialist,
        state_key=BUSINESS_STATE_RESULT,
        agent_name="business_research_agent",
        display_name="Business Specialist",
    ),
    SpecialistConfig(
        entity_type=EntityType.CHARACTER_NAME,
        agent=character_name_specialist,
        state_key=CHARACTER_STATE_RESULT,
        agent_name="character_research_agent",
        display_name="Character Name Specialist",
    ),
    SpecialistConfig(
        entity_type=EntityType.SONG,
        agent=music_specialist,
        state_key=MUSIC_STATE_RESULT,
        agent_name="music_research_agent",
        display_name="Music Specialist",
    ),
    SpecialistConfig(
        entity_type=EntityType.LOGO_BRAND,
        agent=trademark_brand_specialist,
        state_key=TRADEMARK_STATE_RESULT,
        agent_name="trademark_brand_research_agent",
        display_name="Trademark/Brand Specialist",
    ),
    SpecialistConfig(
        entity_type=EntityType.ADDRESS,
        agent=address_specialist,
        state_key=ADDRESS_STATE_RESULT,
        agent_name="address_research_agent",
        display_name="Address Specialist",
    ),
    SpecialistConfig(
        entity_type=EntityType.QUOTE_OR_LITERARY_REFERENCE,
        agent=literary_reference_specialist,
        state_key=LITERARY_STATE_RESULT,
        agent_name="literary_reference_research_agent",
        display_name="Literary Reference Specialist",
    ),
]

# Map entity types to specialist configurations
ENTITY_TO_SPECIALIST: Dict[EntityType, SpecialistConfig] = {
    cfg.entity_type: cfg for cfg in SPECIALISTS
}

# Unimplemented entity types (will be skipped with warning)
UNIMPLEMENTED_TYPES = {
    EntityType.PHONE_NUMBER,
    EntityType.LICENSE_PLATE,
    EntityType.REAL_PUBLIC_FIGURE,
}


async def run_extraction(
    screenplay_text: str,
    user_id: str = "orchestrator",
    on_progress: ProgressCallback | None = None,
    run_id: str | None = None,
) -> Entities:
    """Run extraction agent on screenplay text."""
    print("\n" + "="*80)
    print("STEP 1: EXTRACTION AGENT")
    print("="*80)

    start_time = time.perf_counter()
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id="extraction",
            agent_name="Extraction Agent",
            phase="extraction",
            status="running",
        ),
    )

    async def _run_extraction_once() -> str:
        session_service = InMemorySessionService()
        runner = Runner(
            agent=extractor,
            app_name="orchestrator_extraction",
            session_service=session_service,
        )
        session_id = f"extraction-{uuid.uuid4().hex[:8]}"
        await session_service.create_session(
            app_name="orchestrator_extraction",
            user_id=user_id,
            session_id=session_id,
        )
        final_text = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=screenplay_text)],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
        if not final_text:
            raise RuntimeError("Extraction agent returned no final response")
        return final_text

    final_text = await _retry_on_transient(
        _run_extraction_once,
        label="Extraction",
        attempts=5,
        base_delay=3.0,
    )

    # Parse the JSON response
    try:
        parsed = json.loads(final_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing extraction output: {e}")
        print(f"Raw output:\n{final_text}")
        raise

    # Add metadata
    parsed["metadata"] = {
        "model_used": get_gemini_model(),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "extraction_agent_version": "0.1.0",
        "total_pages_scanned": parsed.get("metadata", {}).get("total_pages_scanned", 0),
    }

    entities = Entities.model_validate(parsed)

    # If a stable run_id was supplied by the caller (from /extract-script),
    # override the auto-generated one so the file upload, pipeline, and
    # Firestore document all share the same identity.
    if run_id is not None:
        entities = entities.model_copy(update={"run_id": run_id})

    print(f"\nExtracted {entities.entity_count} entities:")
    for i, entity in enumerate(entities.entities, 1):
        risk_str = entity.risk_category.value if entity.risk_category else "None"
        print(f"  {i:3d}. {entity.name[:40]:40} "
              f"type={entity.entity_type.value:30} "
              f"risk={risk_str:15} "
              f"conf={entity.confidence:.2f}")

    duration = time.perf_counter() - start_time
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_complete",
            agent_id="extraction",
            agent_name="Extraction Agent",
            phase="extraction",
            status="success",
            duration_seconds=round(duration, 2),
            output=_extraction_output(entities),
        ),
    )

    return entities


async def run_grounding_check(
    screenplay_text: str,
    entities: Entities,
    user_id: str = "orchestrator",
    on_progress: ProgressCallback | None = None,
) -> Entities:
    """Run deterministic grounding and return filtered Entities.

    Uses Python string matching against the screenplay (no LLM). The legacy
    LLM grounding agent remains available in agents/grounding_check_agent.py
    but is not invoked on the live clearance path.
    """
    print("\n" + "=" * 80)
    print("STEP 2: GROUNDING CHECK (DETERMINISTIC)")
    print("=" * 80)

    start_time = time.perf_counter()
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id="grounding",
            agent_name="Grounding Check",
            phase="grounding",
            status="running",
        ),
    )

    if entities.entity_count == 0:
        print("\nNo entities to ground.")
        duration = time.perf_counter() - start_time
        await _emit_progress(
            on_progress,
            PipelineProgressEvent(
                event="agent_complete",
                agent_id="grounding",
                agent_name="Grounding Check",
                phase="grounding",
                status="success",
                duration_seconds=round(duration, 2),
                output=_grounding_output(
                    extracted_count=0,
                    grounded=[],
                    rejected=[],
                ),
            ),
        )
        return entities

    # Deterministic grounding (no LLM). Legacy agent:
    # agents/grounding_check_agent.py
    filtered, grounded, rejected = ground_entities(screenplay_text, entities)

    print("\nGrounding Check:")
    for entity in grounded:
        print(f"  [OK] {entity.name} — grounded")
    for entity in rejected:
        print(f"  [X] {entity.name} — not grounded")

    print(
        f"\nGrounding summary: {entities.entity_count} extracted, "
        f"{len(grounded)} grounded, {len(rejected)} rejected"
    )

    duration = time.perf_counter() - start_time
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_complete",
            agent_id="grounding",
            agent_name="Grounding Check",
            phase="grounding",
            status="success",
            duration_seconds=round(duration, 2),
            output=_grounding_output(
                extracted_count=entities.entity_count,
                grounded=grounded,
                rejected=rejected,
            ),
        ),
    )

    return filtered


async def process_entity(
    entity: Entity,
    specialist_config: SpecialistConfig,
    user_id: str,
    entity_index: int,
    total_entities: int,
    on_progress: ProgressCallback | None = None,
    session_cache: Dict[str, ResearchResult] | None = None,
    session_locks: Dict[str, asyncio.Lock] | None = None,
    research_metrics: ResearchMetrics | None = None,
) -> EntityResult:
    """Process a single entity with its specialist agent."""
    agent_id = f"specialist_{entity.entity_type.value}_{entity.entity_id[:8]}"
    start_time = time.perf_counter()
    cache_key = entity_cache_key(entity.entity_type, entity.name)

    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id=agent_id,
            agent_name=specialist_config.display_name,
            phase="specialist",
            status="running",
            entity_name=entity.name,
            entity_type=entity.entity_type.value,
            message=f"Researching entity {entity_index}/{total_entities}",
        ),
    )
    
    print(f"\nProcessing entity {entity_index}/{total_entities}:")
    print(f"  Type: {specialist_config.display_name}")
    print(f"  Name: {entity.name}")
    print(f"  Context: {entity.context[:60]}..." if entity.context else "  Context: None")

    base_prompt = (
        f"Research the following screenplay Entity. "
        f"entity_type must be treated as {entity.entity_type.value}.\n\n"
        f"{entity.model_dump_json(indent=2)}"
    )
    rag_prompt_prefix = ""

    async def _run_specialist_once() -> ResearchResult | None:
        prompt = f"{rag_prompt_prefix}{base_prompt}"
        app_name = (
            f"orchestrator_{entity.entity_type.value}_{entity_index}_"
            f"{int(time.perf_counter() * 1000)}"
        )
        runner = InMemoryRunner(
            app_name=app_name,
            agent=specialist_config.create_agent(),
        )
        session = await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
        )

        research_texts: List[str] = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ):
            if not event.content or not event.content.parts:
                continue

            for part in event.content.parts:
                text = getattr(part, "text", None)
                if text and getattr(event, "author", None) == specialist_config.agent_name:
                    research_texts.append(text)

        refreshed = await runner.session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session.id,
        )

        raw_result = (refreshed.state or {}).get(specialist_config.state_key) if refreshed else None
        if raw_result is None and research_texts:
            raw_result = research_texts[-1]

        if isinstance(raw_result, str):
            try:
                raw_result = json.loads(raw_result)
            except json.JSONDecodeError:
                raw_result = {"raw_text": raw_result}

        if raw_result is None:
            return None
        return ResearchResult.model_validate(raw_result)

    async def _resolve_research() -> tuple[ResearchResult | None, ResearchSource | None]:
        """Return cached research or run the specialist (with within-run dedup)."""

        nonlocal rag_prompt_prefix
        metrics = research_metrics or get_research_metrics()

        def _adapt(cached: ResearchResult) -> ResearchResult:
            return adapt_research_for_entity(cached, entity)

        def _store_research(generic: ResearchResult) -> bool:
            """
            Store research in cache and vector index.
            Returns True if fully successful, False if RAG indexing failed.
            """
            rag_indexed = False
            if research_cache_enabled():
                get_research_cache().upsert(
                    entity.entity_type,
                    entity.name,
                    generic,
                )
            try:
                rag_indexed = index_research_result(
                    entity.entity_type,
                    entity.name,
                    generic,
                    context=entity.context,
                )
            except Exception as e:
                # Critical errors (dimension mismatch) should not be silently ignored
                logger.error(
                    "RAG indexing failed critically for %s: %s. "
                    "This may affect future semantic searches.",
                    entity.name,
                    e,
                )
                # Don't let RAG indexing failures break the entire pipeline
                rag_indexed = False
            if session_cache is not None:
                session_cache[cache_key] = generic
            return rag_indexed

        async def _lookup_persistent() -> ResearchResult | None:
            if not research_cache_enabled():
                return None
            cached = get_research_cache().lookup(entity.entity_type, entity.name)
            if cached is None:
                return None
            print(f"  Research cache HIT (persistent): {cache_key}")
            return cached

        async def _lookup_rag() -> ResearchResult | None:
            nonlocal rag_prompt_prefix
            match = await retrieve_similar_research(entity)
            if match is None:
                return None
            if match.tier == "high":
                print(
                    f"  Research RAG HIT (high {match.score:.2f}): "
                    f"{match.source_name} -> {entity.name}"
                )
                synthesized = await synthesize_rag_result(
                    entity,
                    match.result,
                    source_name=match.source_name,
                )
                generic = synthesized.model_copy(update={"entity_id": None})
                _store_research(generic)
                metrics.record(ResearchSource.RAG_HIGH)
                return generic
            print(
                f"  Research RAG HIT (medium {match.score:.2f}): "
                f"augmenting prompt from {match.source_name}"
            )
            rag_prompt_prefix = build_rag_prompt_context(match)
            return None

        async def _run_specialist() -> ResearchResult | None:
            had_rag_context = bool(rag_prompt_prefix)
            result = await _retry_on_transient(
                _run_specialist_once,
                label=f"{specialist_config.display_name} ({entity.name})",
            )
            if result and is_cacheable_research(result):
                generic = result.model_copy(update={"entity_id": None})
                _store_research(generic)
            metrics.record(
                ResearchSource.RAG_MEDIUM_PARALLEL
                if had_rag_context
                else ResearchSource.PARALLEL
            )
            return result

        if session_cache is not None and session_locks is not None:
            lock = session_locks.setdefault(cache_key, asyncio.Lock())
            async with lock:
                if cache_key in session_cache:
                    print(f"  Research cache HIT (session): {cache_key}")
                    metrics.record(ResearchSource.SESSION_CACHE)
                    return _adapt(session_cache[cache_key]), ResearchSource.SESSION_CACHE
                cached = await _lookup_persistent()
                if cached is not None:
                    session_cache[cache_key] = cached
                    metrics.record(ResearchSource.PERSISTENT_CACHE)
                    return _adapt(cached), ResearchSource.PERSISTENT_CACHE
                rag_hit = await _lookup_rag()
                if rag_hit is not None:
                    return _adapt(rag_hit), ResearchSource.RAG_HIGH
                result = await _run_specialist()
                source = (
                    ResearchSource.RAG_MEDIUM_PARALLEL
                    if rag_prompt_prefix
                    else ResearchSource.PARALLEL
                )
                return result, source

        cached = await _lookup_persistent()
        if cached is not None:
            metrics.record(ResearchSource.PERSISTENT_CACHE)
            return _adapt(cached), ResearchSource.PERSISTENT_CACHE
        rag_hit = await _lookup_rag()
        if rag_hit is not None:
            return _adapt(rag_hit), ResearchSource.RAG_HIGH
        result = await _run_specialist()
        source = (
            ResearchSource.RAG_MEDIUM_PARALLEL
            if rag_prompt_prefix
            else ResearchSource.PARALLEL
        )
        return result, source

    try:
        research_result, research_source = await _resolve_research()

        processing_time = time.perf_counter() - start_time
        
        success = research_result is not None and research_result.status != ResearchStatus.TOOL_FAILURE
        
        print(f"  Result: {'SUCCESS' if success else 'FAILED'} "
              f"(time: {processing_time:.1f}s)")
        if research_result:
            print(f"  Status: {research_result.status.value}")
            print(f"  Confidence: {research_result.confidence:.2f}")
            print(f"  Citations: {len(research_result.citations)}")

        entity_result = EntityResult(
            entity=entity,
            research_result=research_result,
            specialist_config=specialist_config,
            processing_time=processing_time,
            success=success,
            error=None,
            research_source=research_source.value if research_source else None,
        )
        duration = time.perf_counter() - start_time
        await _emit_progress(
            on_progress,
            PipelineProgressEvent(
                event="agent_complete",
                agent_id=agent_id,
                agent_name=specialist_config.display_name,
                phase="specialist",
                status="success" if success else "failed",
                duration_seconds=round(duration, 2),
                entity_name=entity.name,
                entity_type=entity.entity_type.value,
                output=_specialist_output(entity_result),
            ),
        )
        return entity_result
        
    except Exception as e:
        processing_time = time.perf_counter() - start_time
        
        print(f"  Result: ERROR (time: {processing_time:.1f}s)")
        print(f"  Error: {str(e)}")

        # Soft-fail transient Gemini overload so the pipeline can continue
        # (risk scoring will assign caution when research_result is missing).
        # Do not put exception text on public progress events.
        if _is_transient_gemini_error(e):
            error_message = "Research temporarily unavailable. The pipeline will continue."
        else:
            error_message = "Specialist research could not be completed."

        entity_result = EntityResult(
            entity=entity,
            research_result=None,
            specialist_config=specialist_config,
            processing_time=processing_time,
            success=False,
            error=error_message,
            research_source=ResearchSource.FAILED.value,
        )
        metrics = research_metrics or get_research_metrics()
        metrics.record(ResearchSource.FAILED)
        duration = time.perf_counter() - start_time
        await _emit_progress(
            on_progress,
            PipelineProgressEvent(
                event="agent_complete",
                agent_id=agent_id,
                agent_name=specialist_config.display_name,
                phase="specialist",
                status="failed",
                duration_seconds=round(duration, 2),
                entity_name=entity.name,
                entity_type=entity.entity_type.value,
                output=_specialist_output(entity_result),
                message=error_message,
            ),
        )
        return entity_result


def _pipeline_concurrency_limit() -> int:
    """Max concurrent Gemini-heavy agent runs (specialists + risk scoring).

    Reads PIPELINE_CONCURRENCY, then SPECIALIST_CONCURRENCY, default 2.
    Lower values reduce 503/high-demand failures; higher values finish faster.
    """
    raw = (
        os.getenv("PIPELINE_CONCURRENCY")
        or os.getenv("SPECIALIST_CONCURRENCY")
        or "2"
    ).strip()
    try:
        value = int(raw)
    except ValueError:
        value = 2
    return max(1, value)


def _specialist_concurrency_limit() -> int:
    """Backward-compatible alias for specialist concurrency."""
    return _pipeline_concurrency_limit()


async def process_entities(
    entities: Entities,
    user_id: str = "orchestrator",
    on_progress: ProgressCallback | None = None,
) -> Dict[EntityType, List[EntityResult]]:
    """Process all grounded entities with specialist agents in parallel."""
    print("\n" + "="*80)
    print("STEP 3: SPECIALIST PROCESSING (PARALLEL)")
    print("="*80)
    
    # Group entities by type
    entities_by_type: Dict[EntityType, List[Entity]] = {}
    for entity in entities.entities:
        if entity.entity_type not in entities_by_type:
            entities_by_type[entity.entity_type] = []
        entities_by_type[entity.entity_type].append(entity)
    
    work_items: List[tuple[Entity, SpecialistConfig]] = []
    for specialist_config in SPECIALISTS:
        for entity in entities_by_type.get(specialist_config.entity_type, []):
            work_items.append((entity, specialist_config))

    total_to_process = len(work_items)
    if total_to_process == 0:
        for entity_type in UNIMPLEMENTED_TYPES:
            if entity_type in entities_by_type:
                count = len(entities_by_type[entity_type])
                print(
                    f"\n⚠️  WARNING: {entity_type.value} entities ({count} found) "
                    "- no specialist implemented yet"
                )
        return {}

    type_counts: Dict[EntityType, int] = {}
    for entity, specialist_config in work_items:
        type_counts[specialist_config.entity_type] = (
            type_counts.get(specialist_config.entity_type, 0) + 1
        )
    for entity_type, count in type_counts.items():
        display = ENTITY_TO_SPECIALIST[entity_type].display_name
        print(f"\n{display}: {count} entities")

    concurrency = _specialist_concurrency_limit()
    print(
        f"\nLaunching {total_to_process} specialist tasks "
        f"(concurrency limit={concurrency})..."
    )
    semaphore = asyncio.Semaphore(concurrency)
    session_cache: Dict[str, ResearchResult] = {}
    session_locks: Dict[str, asyncio.Lock] = {}
    research_metrics = get_research_metrics()

    async def run_one(
        index: int,
        entity: Entity,
        specialist_config: SpecialistConfig,
    ) -> EntityResult:
        async with semaphore:
            return await process_entity(
                entity=entity,
                specialist_config=specialist_config,
                user_id=user_id,
                entity_index=index,
                total_entities=total_to_process,
                on_progress=on_progress,
                session_cache=session_cache,
                session_locks=session_locks,
                research_metrics=research_metrics,
            )

    gathered = await asyncio.gather(
        *[
            run_one(index, entity, specialist_config)
            for index, (entity, specialist_config) in enumerate(work_items, start=1)
        ]
    )

    results: Dict[EntityType, List[EntityResult]] = {}
    for entity_result in gathered:
        entity_type = entity_result.entity.entity_type
        if entity_type not in results:
            results[entity_type] = []
        results[entity_type].append(entity_result)
    
    # Warn about unimplemented entity types
    for entity_type in UNIMPLEMENTED_TYPES:
        if entity_type in entities_by_type:
            count = len(entities_by_type[entity_type])
            print(f"\n⚠️  WARNING: {entity_type.value} entities ({count} found) - no specialist implemented yet")

    for line in research_metrics.summary_lines():
        print(line)
    research_metrics.log_summary()
    
    return results


def build_fallback_risk_result(entity: Entity, reason: str) -> RiskResult:
    """Build a caution RiskResult when research is unavailable."""
    return RiskResult(
        entity_id=entity.entity_id,
        entity_name=entity.name,
        entity_type=entity.entity_type,
        risk_level=RiskLevel.CAUTION,
        triggered_rule="research_unavailable",
        reasoning=reason,
        evidence=[],
        research_confidence=0.0,
        requires_human_review=entity.requires_human_review,
    )


async def score_entity_risk(
    entity: Entity,
    research_result: ResearchResult,
    user_id: str = "orchestrator",
    entity_index: int = 1,
    total_entities: int = 1,
    on_progress: ProgressCallback | None = None,
) -> RiskResult:
    """Score one entity using the Risk Scoring Agent."""
    agent_id = f"risk_scoring_{entity.entity_id[:8]}"
    start_time = time.perf_counter()

    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id=agent_id,
            agent_name="Risk Scoring Agent",
            phase="risk_scoring",
            status="running",
            entity_name=entity.name,
            entity_type=entity.entity_type.value,
            message=f"Scoring entity {entity_index}/{total_entities}",
        ),
    )

    print(f"\nScoring entity {entity_index}/{total_entities}:")
    print(f"  Name: {entity.name}")
    print(f"  Type: {entity.entity_type.value}")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=risk_scorer,
        app_name="orchestrator_risk_scoring",
        session_service=session_service,
    )

    session_id = f"risk_{entity.entity_id[:8]}"
    await session_service.create_session(
        app_name="orchestrator_risk_scoring",
        user_id=user_id,
        session_id=session_id,
    )

    prompt = build_scoring_prompt(entity, research_result)

    async def _run_scorer() -> str:
        text = None
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                text = event.content.parts[0].text
        if not text:
            raise RuntimeError(
                f"Risk scoring agent returned no final response for {entity.name}"
            )
        return text

    final_text = await _retry_on_transient(
        _run_scorer,
        label=f"Risk scoring ({entity.name})",
    )

    parsed = json.loads(final_text)
    parsed["research_confidence"] = research_result.confidence
    agent_output = RiskResult.model_validate(parsed)
    risk_result = finalize_risk_result(entity, agent_output)

    print(f"  Risk: {risk_result.risk_level.value}")
    print(f"  Rule: {risk_result.triggered_rule}")
    print(f"  Research confidence: {risk_result.research_confidence:.2f}")
    if risk_result.requires_human_review:
        print("  ⚠️  Requires human review")

    duration = time.perf_counter() - start_time
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_complete",
            agent_id=agent_id,
            agent_name="Risk Scoring Agent",
            phase="risk_scoring",
            status="success",
            duration_seconds=round(duration, 2),
            entity_name=entity.name,
            entity_type=entity.entity_type.value,
            output=_risk_scoring_output(risk_result),
        ),
    )

    return risk_result


async def run_risk_scoring(
    entity_results: Dict[EntityType, List[EntityResult]],
    user_id: str = "orchestrator",
    on_progress: ProgressCallback | None = None,
) -> Dict[EntityType, List[EntityResult]]:
    """Run risk scoring for all entities with research results in parallel."""
    print("\n" + "=" * 80)
    print("STEP 4: RISK SCORING AGENT (PARALLEL)")
    print("=" * 80)

    flat_results = [
        result
        for results_list in entity_results.values()
        for result in results_list
    ]
    scoreable = [result for result in flat_results if result.research_result is not None]
    total = len(scoreable)

    if not flat_results:
        print("\nNo entities to score.")
        return entity_results

    if total == 0:
        print("\nNo research results available to score.")
        scored_results: Dict[EntityType, List[EntityResult]] = {}
        for result in flat_results:
            fallback = build_fallback_risk_result(
                result.entity,
                "Specialist research was not available; manual review recommended.",
            )
            scored_results.setdefault(result.entity.entity_type, []).append(
                EntityResult(
                    entity=result.entity,
                    research_result=result.research_result,
                    specialist_config=result.specialist_config,
                    processing_time=result.processing_time,
                    success=result.success,
                    error=result.error,
                    risk_result=fallback,
                )
            )
            print(f"\n  ✗ {result.entity.name} — no research; assigned caution")
        return scored_results

    print(f"\nLaunching {total} risk scoring tasks "
          f"(concurrency limit={_pipeline_concurrency_limit()})...")

    scoring_semaphore = asyncio.Semaphore(_pipeline_concurrency_limit())

    async def score_one(
        result: EntityResult,
        entity_index: int,
    ) -> EntityResult:
        if result.research_result is None:
            fallback = build_fallback_risk_result(
                result.entity,
                "Specialist research was not available; manual review recommended.",
            )
            print(f"\n  ✗ {result.entity.name} — no research; assigned caution")
            return EntityResult(
                entity=result.entity,
                research_result=result.research_result,
                specialist_config=result.specialist_config,
                processing_time=result.processing_time,
                success=result.success,
                error=result.error,
                risk_result=fallback,
            )

        async with scoring_semaphore:
            try:
                risk_result = await score_entity_risk(
                    entity=result.entity,
                    research_result=result.research_result,
                    user_id=user_id,
                    entity_index=entity_index,
                    total_entities=total,
                    on_progress=on_progress,
                )
            except Exception as exc:
                if _is_transient_gemini_error(exc):
                    print(
                        f"\n  ✗ {result.entity.name} — Gemini unavailable after retries; "
                        "assigned caution"
                    )
                    risk_result = build_fallback_risk_result(
                        result.entity,
                        "Risk scoring temporarily unavailable (Gemini high demand); "
                        "manual review recommended.",
                    )
                else:
                    raise
        return EntityResult(
            entity=result.entity,
            research_result=result.research_result,
            specialist_config=result.specialist_config,
            processing_time=result.processing_time,
            success=result.success,
            error=result.error,
            risk_result=risk_result,
        )

    scoreable_index = {
        id(result): index for index, result in enumerate(scoreable, start=1)
    }
    scored_flat = await asyncio.gather(
        *[
            score_one(
                result,
                scoreable_index.get(id(result), 1),
            )
            for result in flat_results
        ]
    )

    scored_results: Dict[EntityType, List[EntityResult]] = {}
    for entity_result in scored_flat:
        scored_results.setdefault(entity_result.entity.entity_type, []).append(entity_result)

    clear_count = sum(
        1
        for results in scored_results.values()
        for result in results
        if result.risk_result and result.risk_result.risk_level == RiskLevel.CLEAR
    )
    caution_count = sum(
        1
        for results in scored_results.values()
        for result in results
        if result.risk_result and result.risk_result.risk_level == RiskLevel.CAUTION
    )
    high_risk_count = sum(
        1
        for results in scored_results.values()
        for result in results
        if result.risk_result and result.risk_result.risk_level == RiskLevel.HIGH_RISK
    )

    print(
        f"\nRisk scoring summary: {clear_count} clear, "
        f"{caution_count} caution, {high_risk_count} high_risk"
    )

    return scored_results


async def run_summary(
    entity_results: Dict[EntityType, List[EntityResult]],
    script_title: str | None = None,
    user_id: str = "orchestrator",
    on_progress: ProgressCallback | None = None,
) -> SummaryResult:
    """Run summary agent over completed risk-scoring results."""
    print("\n" + "=" * 80)
    print("STEP 5: SUMMARY AGENT")
    print("=" * 80)

    start_time = time.perf_counter()
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id="summary",
            agent_name="Summary Agent",
            phase="summary",
            status="running",
        ),
    )

    risk_results = collect_risk_results(entity_results)
    if not risk_results:
        empty = SummaryResult(
            overall_summary="No entities were scored in this clearance run.",
            total_entities=0,
            clear_count=0,
            caution_count=0,
            high_risk_count=0,
            priority_items=[],
        )
        print("\nNo risk results to summarise.")
        duration = time.perf_counter() - start_time
        await _emit_progress(
            on_progress,
            PipelineProgressEvent(
                event="agent_complete",
                agent_id="summary",
                agent_name="Summary Agent",
                phase="summary",
                status="success",
                duration_seconds=round(duration, 2),
                output=_summary_output(empty),
            ),
        )
        return empty

    session_service = InMemorySessionService()
    runner = Runner(
        agent=summarizer,
        app_name="orchestrator_summary",
        session_service=session_service,
    )

    await session_service.create_session(
        app_name="orchestrator_summary",
        user_id=user_id,
        session_id="summary",
    )

    prompt = build_summary_prompt(risk_results, script_title=script_title)
    final_text = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id="summary",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    if not final_text:
        raise RuntimeError("Summary agent returned no final response")

    parsed = json.loads(final_text)
    agent_output = SummaryResult.model_validate(parsed)
    summary = finalize_summary_result(risk_results, agent_output)

    print(f"\nClearance summary ({summary.total_entities} entities):")
    print(f"  Clear: {summary.clear_count}")
    print(f"  Caution: {summary.caution_count}")
    print(f"  High risk: {summary.high_risk_count}")
    print(f"\n{summary.overall_summary[:300]}...")
    if summary.priority_items:
        print("\nPriority items:")
        for item in summary.priority_items:
            print(f"  • {item}")

    duration = time.perf_counter() - start_time
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_complete",
            agent_id="summary",
            agent_name="Summary Agent",
            phase="summary",
            status="success",
            duration_seconds=round(duration, 2),
            output=_summary_output(summary),
        ),
    )

    return summary


def run_legal_review_setup(
    entity_results: Dict[EntityType, List[EntityResult]],
    *,
    run_id: str,
    script_id: str,
    script_title: str | None = None,
    summary_result: SummaryResult | None = None,
) -> LegalReviewPackage:
    """
    Prepare the clearance run for human legal review.

    All entities default to NEEDS_REVIEW. No approvals are inferred.
    """
    print("\n" + "=" * 80)
    print("STEP 6: LEGAL REVIEW (HUMAN DECISION REQUIRED)")
    print("=" * 80)

    package = build_legal_review_package(
        entity_results,
        run_id=run_id,
        script_id=script_id,
        script_title=script_title,
        summary_result=summary_result,
    )

    pending_required = get_pending_required_reviews(package)
    print(f"\nEntities awaiting legal review: {package.pending_review_count}")
    print(f"High-risk / human-review items requiring explicit decision: {len(pending_required)}")

    for record in pending_required:
        print(
            f"  • {record.entity_name} — AI risk: {record.ai_risk_level.value} "
            f"(decision: {record.decision.value})"
        )

    if pending_required:
        print(
            "\n⚠️  No approvals inferred. A human reviewer must explicitly "
            "record APPROVED, BLOCKED, or leave as NEEDS_REVIEW."
        )
    else:
        print("\nNo high-risk or human-review entities require explicit decisions.")

    return package


def run_gatekeeper(legal_review: LegalReviewPackage) -> GatekeeperResult:
    """Evaluate clearance policy and determine if the run may proceed."""
    print("\n" + "=" * 80)
    print("STEP 7: GATEKEEPER")
    print("=" * 80)

    result = evaluate_clearance(legal_review)

    print(f"\nGatekeeper decision: {result.status.value}")
    print(f"Reason: {result.reason.value}")
    print(f"Message: {result.message}")

    if result.blocking_entity_ids:
        print(f"Blocking entities: {', '.join(result.blocking_entity_ids)}")

    if result.cleared_for_export:
        print("\n✓ Cleared for final report/export")
    else:
        print("\n✗ BLOCKED — final report must not be presented as approved/cleared")

    return result


def generate_report(
    screenplay_path: str,
    extracted_entities: Entities,
    entity_results: Dict[EntityType, List[EntityResult]],
    start_time: datetime,
    end_time: datetime,
    summary_result: SummaryResult | None = None,
    legal_review: LegalReviewPackage | None = None,
    gatekeeper_result: GatekeeperResult | None = None,
) -> Dict:
    """Generate a comprehensive clearance report."""
    
    # Calculate statistics
    total_entities = extracted_entities.entity_count
    successful_researches = sum(
        sum(1 for r in results if r.success)
        for results in entity_results.values()
    )
    failed_researches = sum(
        sum(1 for r in results if not r.success)
        for results in entity_results.values()
    )
    
    # Risk categorization from Risk Scoring Agent
    clear_entities = []
    caution_entities = []
    high_risk_entities = []

    for results_list in entity_results.values():
        for result in results_list:
            if result.risk_result:
                if result.risk_result.risk_level == RiskLevel.HIGH_RISK:
                    high_risk_entities.append(result)
                elif result.risk_result.risk_level == RiskLevel.CAUTION:
                    caution_entities.append(result)
                else:
                    clear_entities.append(result)
            elif result.research_result:
                caution_entities.append(result)
            else:
                caution_entities.append(result)
    
    # Generate report
    report = {
        "metadata": {
            "screenplay_file": screenplay_path,
            "pipeline_version": "1.0.0",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "model_used": get_gemini_model(),
            "cleared_for_export": (
                gatekeeper_result.cleared_for_export if gatekeeper_result else False
            ),
            "clearance_status": (
                gatekeeper_result.status.value if gatekeeper_result else "blocked"
            ),
        },
        "statistics": {
            "total_entities_extracted": total_entities,
            "entities_researched": successful_researches + failed_researches,
            "successful_researches": successful_researches,
            "failed_researches": failed_researches,
            "clear_entities": len(clear_entities),
            "caution_entities": len(caution_entities),
            "high_risk_entities": len(high_risk_entities),
        },
        "entities_by_type": {},
        "high_risk_findings": [],
        "recommendations": [],
        "summary": summary_result.model_dump(mode="json") if summary_result else None,
        "legal_review": legal_review.model_dump(mode="json") if legal_review else None,
        "gatekeeper": gatekeeper_result.model_dump(mode="json") if gatekeeper_result else None,
    }
    
    # Add detailed entity results by type
    for entity_type, results_list in entity_results.items():
        report["entities_by_type"][entity_type.value] = {
            "count": len(results_list),
            "successful": sum(1 for r in results_list if r.success),
            "failed": sum(1 for r in results_list if not r.success),
            "entities": [
                {
                    "name": r.entity.name,
                    "context": r.entity.context,
                    "extraction_confidence": r.entity.confidence,
                    "research_success": r.success,
                    "research_confidence": r.research_result.confidence if r.research_result else None,
                    "research_status": r.research_result.status.value if r.research_result else None,
                    "citations_count": len(r.research_result.citations) if r.research_result else 0,
                    "risk_level": r.risk_result.risk_level.value if r.risk_result else None,
                    "triggered_rule": r.risk_result.triggered_rule if r.risk_result else None,
                    "reasoning": r.risk_result.reasoning if r.risk_result else None,
                    "requires_human_review": r.risk_result.requires_human_review if r.risk_result else r.entity.requires_human_review,
                }
                for r in results_list
            ]
        }
    
    # Add high risk findings
    for result in high_risk_entities:
        if result.risk_result:
            report["high_risk_findings"].append({
                "entity_name": result.entity.name,
                "entity_type": result.entity.entity_type.value,
                "risk_level": result.risk_result.risk_level.value,
                "triggered_rule": result.risk_result.triggered_rule,
                "reasoning": result.risk_result.reasoning,
                "research_confidence": result.risk_result.research_confidence,
                "research_status": result.research_result.status.value if result.research_result else None,
                "finding": (
                    result.research_result.finding[:200] + "..."
                    if result.research_result and len(result.research_result.finding) > 200
                    else (result.research_result.finding if result.research_result else None)
                ),
                "requires_human_review": result.risk_result.requires_human_review,
            })
    
    # Generate recommendations
    if high_risk_entities:
        report["recommendations"].append(
            f"{len(high_risk_entities)} high-risk entities identified. Legal review strongly recommended."
        )
    if caution_entities:
        report["recommendations"].append(
            f"{len(caution_entities)} caution-level entities identified. Consider legal consultation."
        )
    if failed_researches > 0:
        report["recommendations"].append(
            f"{failed_researches} research attempts failed. Manual verification needed."
        )
    
    if not high_risk_entities and not caution_entities and (
        not gatekeeper_result or gatekeeper_result.cleared_for_export
    ):
        report["recommendations"].append(
            "No significant risks identified. Script appears to be legally clear."
        )

    if gatekeeper_result and gatekeeper_result.status == GatekeeperStatus.BLOCKED:
        report["recommendations"].insert(
            0,
            f"GATEKEEPER BLOCKED: {gatekeeper_result.message}",
        )
    elif gatekeeper_result and gatekeeper_result.cleared_for_export:
        report["recommendations"].append(
            "Gatekeeper cleared this run for final report/export."
        )
    
    return report


async def run_clearance_pipeline(
    screenplay_text: str,
    *,
    screenplay_path: str = "<inline>",
    user_id: str = "orchestrator",
    legal_review: LegalReviewPackage | None = None,
    on_progress: ProgressCallback | None = None,
    run_id: str | None = None,
) -> ClearancePipelineResult:
    """
    Run the full clearance pipeline from screenplay text to gatekeeper result.

    If ``legal_review`` is supplied, it is used instead of building a fresh
    package (for testing explicit human decisions). Otherwise a new legal
    review package is created with all entities defaulting to NEEDS_REVIEW.
    """
    start_time = datetime.now()

    extracted_entities = await run_extraction(
        screenplay_text,
        user_id=user_id,
        on_progress=on_progress,
        run_id=run_id,
    )
    if extracted_entities.entity_count == 0:
        raise RuntimeError("No entities extracted from screenplay")

    grounded_entities = await run_grounding_check(
        screenplay_text,
        extracted_entities,
        user_id=user_id,
        on_progress=on_progress,
    )
    if grounded_entities.entity_count == 0:
        raise RuntimeError("No grounded entities remain after grounding check")

    entity_results = await process_entities(
        grounded_entities,
        user_id=user_id,
        on_progress=on_progress,
    )
    entity_results = await run_risk_scoring(
        entity_results,
        user_id=user_id,
        on_progress=on_progress,
    )
    summary_result = await run_summary(
        entity_results,
        script_title=grounded_entities.script_title,
        user_id=user_id,
        on_progress=on_progress,
    )

    legal_start = time.perf_counter()
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id="legal_review",
            agent_name="Legal Review Setup",
            phase="legal_review",
            status="running",
        ),
    )
    if legal_review is None:
        legal_review = run_legal_review_setup(
            entity_results,
            run_id=grounded_entities.run_id,
            script_id=grounded_entities.script_id,
            script_title=grounded_entities.script_title,
            summary_result=summary_result,
        )
    legal_duration = time.perf_counter() - legal_start
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_complete",
            agent_id="legal_review",
            agent_name="Legal Review Setup",
            phase="legal_review",
            status="success",
            duration_seconds=round(legal_duration, 2),
            output=_legal_review_output(legal_review),
        ),
    )

    gatekeeper_start = time.perf_counter()
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_start",
            agent_id="gatekeeper",
            agent_name="Gatekeeper",
            phase="gatekeeper",
            status="running",
        ),
    )
    gatekeeper_result = run_gatekeeper(legal_review)
    gatekeeper_duration = time.perf_counter() - gatekeeper_start
    await _emit_progress(
        on_progress,
        PipelineProgressEvent(
            event="agent_complete",
            agent_id="gatekeeper",
            agent_name="Gatekeeper",
            phase="gatekeeper",
            status="success",
            duration_seconds=round(gatekeeper_duration, 2),
            output=_gatekeeper_output(gatekeeper_result),
        ),
    )
    end_time = datetime.now()
    report = generate_report(
        screenplay_path=screenplay_path,
        extracted_entities=extracted_entities,
        entity_results=entity_results,
        start_time=start_time,
        end_time=end_time,
        summary_result=summary_result,
        legal_review=legal_review,
        gatekeeper_result=gatekeeper_result,
    )

    return ClearancePipelineResult(
        screenplay_path=screenplay_path,
        screenplay_text=screenplay_text,
        extracted_entities=extracted_entities,
        grounded_entities=grounded_entities,
        entity_results=entity_results,
        summary_result=summary_result,
        legal_review=legal_review,
        gatekeeper_result=gatekeeper_result,
        report=report,
        start_time=start_time,
        end_time=end_time,
    )


async def main_async(screenplay_path: str, output_file: Optional[str] = None) -> int:
    """Main async orchestration function."""
    start_time = datetime.now()
    
    print("\n" + "="*80)
    print("SCRIPT CLEARANCE ORCHESTRATOR")
    print("="*80)
    print(f"Screenplay: {screenplay_path}")
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Check API key
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY environment variable required")
        print("Set it in .env file or export in your shell")
        return 1
    
    # Read screenplay
    try:
        screenplay_text = Path(screenplay_path).read_text(encoding="utf-8")
        print(f"Screenplay length: {len(screenplay_text)} characters")
    except Exception as e:
        print(f"ERROR: Failed to read screenplay file: {e}")
        return 1

    try:
        pipeline_result = await run_clearance_pipeline(
            screenplay_text,
            screenplay_path=screenplay_path,
        )
    except RuntimeError as e:
        print(f"Pipeline stopped: {e}")
        return 0
    except Exception as e:
        print(f"ERROR: Pipeline failed: {e}")
        return 1

    extracted_entities = pipeline_result.extracted_entities
    entity_results = pipeline_result.entity_results
    summary_result = pipeline_result.summary_result
    legal_review = pipeline_result.legal_review
    gatekeeper_result = pipeline_result.gatekeeper_result
    report = pipeline_result.report
    start_time = pipeline_result.start_time
    
    # Output results
    print("\n" + "="*80)
    if gatekeeper_result.cleared_for_export:
        print("FINAL REPORT — CLEARED FOR EXPORT")
    else:
        print("FINAL REPORT — BLOCKED (NOT CLEARED FOR EXPORT)")
    print("="*80)
    
    stats = report["statistics"]
    print(f"\nSummary:")
    print(f"  Total entities extracted: {stats['total_entities_extracted']}")
    print(f"  Entities researched: {stats['entities_researched']}")
    print(f"  Successful researches: {stats['successful_researches']}")
    print(f"  Failed researches: {stats['failed_researches']}")
    print(f"  Clear: {stats['clear_entities']}")
    print(f"  Caution: {stats['caution_entities']}")
    print(f"  High risk: {stats['high_risk_entities']}")
    print(f"  Total time: {report['metadata']['duration_seconds']:.1f}s")

    if summary_result:
        print(f"\nClearance Overview:")
        print(f"  {summary_result.overall_summary}")
        if summary_result.priority_items:
            print(f"\nPriority items ({len(summary_result.priority_items)}):")
            for item in summary_result.priority_items:
                print(f"  • {item}")

    if legal_review:
        pending = legal_review.unresolved_required_count
        print(f"\nLegal Review Status:")
        print(f"  Overall decision: {legal_review.overall_decision.value}")
        print(f"  Unresolved required reviews: {pending}")
        if pending:
            print("  ⚠️  Human legal review required before run approval")

    if gatekeeper_result:
        print(f"\nGatekeeper:")
        print(f"  Status: {gatekeeper_result.status.value}")
        print(f"  Reason: {gatekeeper_result.reason.value}")
        print(f"  Cleared for export: {gatekeeper_result.cleared_for_export}")
    
    print(f"\nHigh-risk findings ({len(report['high_risk_findings'])}):")
    for finding in report["high_risk_findings"]:
        print(f"  • {finding['entity_name']} ({finding['entity_type']}) - "
              f"Risk: {finding['risk_level']}")
        print(f"    Rule: {finding['triggered_rule']}")
        if finding["requires_human_review"]:
            print(f"    ⚠️  REQUIRES HUMAN REVIEW")
    
    print(f"\nRecommendations:")
    for rec in report["recommendations"]:
        print(f"  • {rec}")
    
    # Save report to file if requested
    if output_file:
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nFull report saved to: {output_path}")
    else:
        # Save default report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = f"clearance_report_{timestamp}.json"
        with open(default_output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nFull report saved to: {default_output}")
    
    print("\n" + "="*80)
    if gatekeeper_result.cleared_for_export:
        print("PIPELINE COMPLETE — CLEARED FOR EXPORT")
    else:
        print("PIPELINE BLOCKED — FINDINGS RETAINED FOR LEGAL REVIEW")
    print("="*80)
    
    return 0 if gatekeeper_result.cleared_for_export else 2


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestrator for script clearance pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator.py screenplay.txt
  python orchestrator.py screenplay.txt --output report.json
  python orchestrator.py --help
        """
    )
    
    parser.add_argument(
        "screenplay",
        help="Path to screenplay text file"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output file for clearance report (JSON format)",
        default=None
    )
    
    args = parser.parse_args()
    
    # Validate screenplay file exists
    if not Path(args.screenplay).exists():
        print(f"ERROR: Screenplay file not found: {args.screenplay}")
        return 1
    
    # Run the async pipeline
    return asyncio.run(main_async(args.screenplay, args.output))


if __name__ == "__main__":
    sys.exit(main())