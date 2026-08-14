#!/usr/bin/env python3
"""
Orchestrator - Main pipeline for script clearance system.

This orchestrator runs the complete screenplay clearance workflow:
1. Extraction Agent: Reads screenplay text and identifies entities
2. Grounding Check Agent: Validates entities against the screenplay
3. Routing: Sends grounded entities to appropriate specialist agents
4. Specialist Processing: Each entity is researched by its specialist
5. Risk Scoring Agent: Applies rubric to entity + research findings
6. Summary Agent: Produces plain-language clearance overview
7. Results Collection: Compiles scored findings and summary
8. Output: Generates final clearance report

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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

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
    business_specialist,
)
from agents.character_name_specialist import (
    STATE_RESEARCH_RESULT as CHARACTER_STATE_RESULT,
    character_name_specialist,
)
from agents.extraction_agent import extractor
from agents.grounding_check_agent import (
    apply_grounding_filter,
    build_grounding_prompt,
    grounding_checker,
)
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
from schemas.risk_result import RiskLevel, RiskResult
from schemas.summary_result import SummaryResult


@dataclass
class SpecialistConfig:
    """Configuration for a specialist agent."""
    entity_type: EntityType
    agent: object
    state_key: str
    agent_name: str
    display_name: str


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


# Specialist configurations
SPECIALISTS: List[SpecialistConfig] = [
    SpecialistConfig(
        entity_type=EntityType.BUSINESS,
        agent=business_specialist,
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


async def run_extraction(screenplay_text: str, user_id: str = "orchestrator") -> Entities:
    """Run extraction agent on screenplay text."""
    print("\n" + "="*80)
    print("STEP 1: EXTRACTION AGENT")
    print("="*80)
    
    session_service = InMemorySessionService()
    runner = Runner(
        agent=extractor,
        app_name="orchestrator_extraction",
        session_service=session_service
    )
    
    await session_service.create_session(
        app_name="orchestrator_extraction",
        user_id=user_id,
        session_id="extraction"
    )
    
    final_text = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id="extraction",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=screenplay_text)]
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text
    
    if not final_text:
        raise RuntimeError("Extraction agent returned no final response")
    
    # Parse the JSON response
    try:
        parsed = json.loads(final_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing extraction output: {e}")
        print(f"Raw output:\n{final_text}")
        raise
    
    # Add metadata
    parsed["metadata"] = {
        "model_used": "gemini-3.6-flash",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "extraction_agent_version": "0.1.0",
        "total_pages_scanned": parsed.get("metadata", {}).get("total_pages_scanned", 0),
    }
    
    entities = Entities.model_validate(parsed)
    
    print(f"\nExtracted {entities.entity_count} entities:")
    for i, entity in enumerate(entities.entities, 1):
        risk_str = entity.risk_category.value if entity.risk_category else "None"
        print(f"  {i:3d}. {entity.name[:40]:40} "
              f"type={entity.entity_type.value:30} "
              f"risk={risk_str:15} "
              f"conf={entity.confidence:.2f}")
    
    return entities


async def run_grounding_check(
    screenplay_text: str,
    entities: Entities,
    user_id: str = "orchestrator",
) -> Entities:
    """Run grounding check agent and return filtered Entities."""
    print("\n" + "=" * 80)
    print("STEP 2: GROUNDING CHECK AGENT")
    print("=" * 80)

    if entities.entity_count == 0:
        print("\nNo entities to ground.")
        return entities

    session_service = InMemorySessionService()
    runner = Runner(
        agent=grounding_checker,
        app_name="orchestrator_grounding",
        session_service=session_service,
    )

    await session_service.create_session(
        app_name="orchestrator_grounding",
        user_id=user_id,
        session_id="grounding",
    )

    prompt = build_grounding_prompt(screenplay_text, entities)
    final_text = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id="grounding",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    if not final_text:
        raise RuntimeError("Grounding check agent returned no final response")

    try:
        parsed = json.loads(final_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing grounding check output: {e}")
        print(f"Raw output:\n{final_text}")
        raise

    parsed["run_id"] = entities.run_id
    parsed["script_id"] = entities.script_id
    parsed["script_title"] = entities.script_title
    parsed["metadata"] = entities.metadata.model_dump(mode="json")

    agent_output = Entities.model_validate(parsed)
    filtered, grounded, rejected = apply_grounding_filter(entities, agent_output)

    print("\nGrounding Check:")
    for entity in grounded:
        print(f"  ✓ {entity.name} — grounded")
    for entity in rejected:
        print(f"  ✗ {entity.name} — not grounded")

    print(
        f"\nGrounding summary: {entities.entity_count} extracted, "
        f"{len(grounded)} grounded, {len(rejected)} rejected"
    )

    return filtered


async def process_entity(
    entity: Entity,
    specialist_config: SpecialistConfig,
    user_id: str,
    entity_index: int,
    total_entities: int
) -> EntityResult:
    """Process a single entity with its specialist agent."""
    start_time = datetime.now()
    
    print(f"\nProcessing entity {entity_index}/{total_entities}:")
    print(f"  Type: {specialist_config.display_name}")
    print(f"  Name: {entity.name}")
    print(f"  Context: {entity.context[:60]}..." if entity.context else "  Context: None")
    
    app_name = f"orchestrator_{entity.entity_type.value}_{entity_index}"
    runner = InMemoryRunner(app_name=app_name, agent=specialist_config.agent)
    
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id
    )
    
    # Prepare prompt for the specialist
    prompt = (
        f"Research the following screenplay Entity. "
        f"entity_type must be treated as {entity.entity_type.value}.\n\n"
        f"{entity.model_dump_json(indent=2)}"
    )
    
    research_texts: List[str] = []
    
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            ),
        ):
            if not event.content or not event.content.parts:
                continue
            
            for part in event.content.parts:
                text = getattr(part, "text", None)
                if text and getattr(event, "author", None) == specialist_config.agent_name:
                    research_texts.append(text)
        
        # Get research result from session state
        refreshed = await runner.session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session.id
        )
        
        raw_result = (refreshed.state or {}).get(specialist_config.state_key) if refreshed else None
        
        # Fallback to last research text if state not found
        if raw_result is None and research_texts:
            raw_result = research_texts[-1]
        
        if isinstance(raw_result, str):
            try:
                raw_result = json.loads(raw_result)
            except json.JSONDecodeError:
                # If it's not JSON, use it as a text result
                raw_result = {"raw_text": raw_result}
        
        research_result = None
        if raw_result is not None:
            research_result = ResearchResult.model_validate(raw_result)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        success = research_result is not None and research_result.status != ResearchStatus.TOOL_FAILURE
        
        print(f"  Result: {'SUCCESS' if success else 'FAILED'} "
              f"(time: {processing_time:.1f}s)")
        if research_result:
            print(f"  Status: {research_result.status.value}")
            print(f"  Confidence: {research_result.confidence:.2f}")
            print(f"  Citations: {len(research_result.citations)}")
        
        return EntityResult(
            entity=entity,
            research_result=research_result,
            specialist_config=specialist_config,
            processing_time=processing_time,
            success=success,
            error=None
        )
        
    except Exception as e:
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"  Result: ERROR (time: {processing_time:.1f}s)")
        print(f"  Error: {str(e)}")
        
        return EntityResult(
            entity=entity,
            research_result=None,
            specialist_config=specialist_config,
            processing_time=processing_time,
            success=False,
            error=str(e)
        )


async def process_entities(
    entities: Entities,
    user_id: str = "orchestrator"
) -> Dict[EntityType, List[EntityResult]]:
    """Process all entities with their respective specialist agents."""
    print("\n" + "="*80)
    print("STEP 3: SPECIALIST PROCESSING")
    print("="*80)
    
    # Group entities by type
    entities_by_type: Dict[EntityType, List[Entity]] = {}
    for entity in entities.entities:
        if entity.entity_type not in entities_by_type:
            entities_by_type[entity.entity_type] = []
        entities_by_type[entity.entity_type].append(entity)
    
    # Track results
    results: Dict[EntityType, List[EntityResult]] = {}
    
    # Process entities for each implemented specialist
    total_processed = 0
    total_to_process = sum(
        len(entities_by_type.get(cfg.entity_type, []))
        for cfg in SPECIALISTS
        if cfg.entity_type in entities_by_type
    )
    
    for specialist_config in SPECIALISTS:
        entity_type = specialist_config.entity_type
        type_entities = entities_by_type.get(entity_type, [])
        
        if not type_entities:
            continue
        
        print(f"\n{specialist_config.display_name}: {len(type_entities)} entities")
        results[entity_type] = []
        
        for i, entity in enumerate(type_entities, 1):
            total_processed += 1
            result = await process_entity(
                entity=entity,
                specialist_config=specialist_config,
                user_id=user_id,
                entity_index=total_processed,
                total_entities=total_to_process
            )
            results[entity_type].append(result)
    
    # Warn about unimplemented entity types
    for entity_type in UNIMPLEMENTED_TYPES:
        if entity_type in entities_by_type:
            count = len(entities_by_type[entity_type])
            print(f"\n⚠️  WARNING: {entity_type.value} entities ({count} found) - no specialist implemented yet")
    
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
) -> RiskResult:
    """Score one entity using the Risk Scoring Agent."""
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
    final_text = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    if not final_text:
        raise RuntimeError(f"Risk scoring agent returned no final response for {entity.name}")

    parsed = json.loads(final_text)
    parsed["research_confidence"] = research_result.confidence
    agent_output = RiskResult.model_validate(parsed)
    risk_result = finalize_risk_result(entity, agent_output)

    print(f"  Risk: {risk_result.risk_level.value}")
    print(f"  Rule: {risk_result.triggered_rule}")
    print(f"  Research confidence: {risk_result.research_confidence:.2f}")
    if risk_result.requires_human_review:
        print("  ⚠️  Requires human review")

    return risk_result


async def run_risk_scoring(
    entity_results: Dict[EntityType, List[EntityResult]],
    user_id: str = "orchestrator",
) -> Dict[EntityType, List[EntityResult]]:
    """Run risk scoring for all entities with research results."""
    print("\n" + "=" * 80)
    print("STEP 4: RISK SCORING AGENT")
    print("=" * 80)

    scoreable = [
        result
        for results in entity_results.values()
        for result in results
        if result.research_result is not None
    ]
    total = len(scoreable)

    if total == 0:
        print("\nNo research results available to score.")
        return entity_results

    scored_results: Dict[EntityType, List[EntityResult]] = {}
    score_index = 0

    for entity_type, results_list in entity_results.items():
        scored_results[entity_type] = []
        for result in results_list:
            if result.research_result is None:
                fallback = build_fallback_risk_result(
                    result.entity,
                    "Specialist research was not available; manual review recommended.",
                )
                scored_results[entity_type].append(
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
                continue

            score_index += 1
            risk_result = await score_entity_risk(
                entity=result.entity,
                research_result=result.research_result,
                user_id=user_id,
                entity_index=score_index,
                total_entities=total,
            )
            scored_results[entity_type].append(
                EntityResult(
                    entity=result.entity,
                    research_result=result.research_result,
                    specialist_config=result.specialist_config,
                    processing_time=result.processing_time,
                    success=result.success,
                    error=result.error,
                    risk_result=risk_result,
                )
            )

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
) -> SummaryResult:
    """Run summary agent over completed risk-scoring results."""
    print("\n" + "=" * 80)
    print("STEP 5: SUMMARY AGENT")
    print("=" * 80)

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

    return summary


def generate_report(
    screenplay_path: str,
    extracted_entities: Entities,
    entity_results: Dict[EntityType, List[EntityResult]],
    start_time: datetime,
    end_time: datetime,
    summary_result: SummaryResult | None = None,
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
            "model_used": "gemini-3.6-flash",
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
    
    if not high_risk_entities and not caution_entities:
        report["recommendations"].append(
            "No significant risks identified. Script appears to be legally clear."
        )
    
    return report


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
    
    # Run extraction
    try:
        extracted_entities = await run_extraction(screenplay_text)
    except Exception as e:
        print(f"ERROR: Extraction failed: {e}")
        return 1
    
    if extracted_entities.entity_count == 0:
        print("No entities found in screenplay. Pipeline complete.")
        end_time = datetime.now()
        print(f"\nTotal time: {(end_time - start_time).total_seconds():.1f}s")
        return 0

    try:
        grounded_entities = await run_grounding_check(screenplay_text, extracted_entities)
    except Exception as e:
        print(f"ERROR: Grounding check failed: {e}")
        return 1

    if grounded_entities.entity_count == 0:
        print("No grounded entities remain after grounding check. Pipeline complete.")
        end_time = datetime.now()
        print(f"\nTotal time: {(end_time - start_time).total_seconds():.1f}s")
        return 0
    
    # Process grounded entities with specialists
    try:
        entity_results = await process_entities(grounded_entities)
    except Exception as e:
        print(f"ERROR: Specialist processing failed: {e}")
        return 1

    try:
        entity_results = await run_risk_scoring(entity_results)
    except Exception as e:
        print(f"ERROR: Risk scoring failed: {e}")
        return 1

    try:
        summary_result = await run_summary(
            entity_results,
            script_title=grounded_entities.script_title,
        )
    except Exception as e:
        print(f"ERROR: Summary generation failed: {e}")
        return 1
    
    # Generate report
    end_time = datetime.now()
    report = generate_report(
        screenplay_path=screenplay_path,
        extracted_entities=extracted_entities,
        entity_results=entity_results,
        start_time=start_time,
        end_time=end_time,
        summary_result=summary_result,
    )
    
    # Output results
    print("\n" + "="*80)
    print("FINAL REPORT")
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
    print("PIPELINE COMPLETE")
    print("="*80)
    
    return 0


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