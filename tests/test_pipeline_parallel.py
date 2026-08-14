"""
tests/test_pipeline_parallel.py

Verify specialist and risk-scoring stages execute concurrently via asyncio.gather.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from schemas.entities import Entities, Entity, EntityType, ExtractionMetadata, ScriptLocation
from schemas.research_result import ResearchResult, ResearchStatus
from orchestrator import EntityResult, SPECIALISTS, process_entities, run_risk_scoring


def build_entities(count: int) -> Entities:
    entities = [
        Entity(
            entity_id=f"entity-{index}",
            name=f"Test Entity {index}",
            entity_type=EntityType.BUSINESS,
            context=f"Context for entity {index}.",
            location=ScriptLocation(scene_number=1, line_excerpt=f"Entity {index}."),
            confidence=0.9,
        )
        for index in range(count)
    ]
    return Entities(
        run_id="parallel-test-run",
        script_id="parallel-test-script",
        script_title="Parallel Test",
        entities=entities,
        metadata=ExtractionMetadata(
            model_used="test",
            extraction_agent_version="0.0.0",
        ),
    )


async def test_specialists_run_in_parallel() -> bool:
    entities = build_entities(4)
    sleep_seconds = 0.4
    call_times: list[float] = []

    async def slow_process_entity(entity, specialist_config, user_id, entity_index, total_entities):
        call_times.append(time.monotonic())
        await asyncio.sleep(sleep_seconds)
        return EntityResult(
            entity=entity,
            research_result=ResearchResult(
                entity_id=entity.entity_id,
                entity_name=entity.name,
                entity_type=entity.entity_type,
                finding="mock finding",
                confidence=0.8,
                status=ResearchStatus.SUCCESS,
            ),
            specialist_config=specialist_config,
            processing_time=sleep_seconds,
            success=True,
        )

    start = time.monotonic()
    with patch("orchestrator.process_entity", side_effect=slow_process_entity):
        results = await process_entities(entities, user_id="parallel-test")

    elapsed = time.monotonic() - start
    sequential_estimate = sleep_seconds * 4

    if len(results.get(EntityType.BUSINESS, [])) != 4:
        print(f"FAILED: expected 4 results, got {len(results.get(EntityType.BUSINESS, []))}")
        return False

    if elapsed >= sequential_estimate * 0.75:
        print(
            f"FAILED: specialist stage appears sequential "
            f"(elapsed={elapsed:.2f}s, sequential≈{sequential_estimate:.2f}s)"
        )
        return False

    spread = max(call_times) - min(call_times) if call_times else 999
    if spread > sleep_seconds:
        print(f"FAILED: specialist calls not launched concurrently (spread={spread:.2f}s)")
        return False

    print(
        f"PASSED: specialists ran in parallel "
        f"(elapsed={elapsed:.2f}s vs sequential≈{sequential_estimate:.2f}s)"
    )
    return True


async def test_risk_scoring_runs_in_parallel() -> bool:
    sleep_seconds = 0.4
    entity_results = {
        EntityType.BUSINESS: [
            EntityResult(
                entity=Entity(
                    entity_id=f"risk-{index}",
                    name=f"Entity {index}",
                    entity_type=EntityType.BUSINESS,
                    context="context",
                    location=ScriptLocation(scene_number=1, line_excerpt="line"),
                    confidence=0.9,
                ),
                research_result=ResearchResult(
                    entity_id=f"risk-{index}",
                    entity_name=f"Entity {index}",
                    entity_type=EntityType.BUSINESS,
                    finding="finding",
                    confidence=0.8,
                    status=ResearchStatus.SUCCESS,
                ),
                specialist_config=SPECIALISTS[0],
                processing_time=0.1,
                success=True,
            )
            for index in range(3)
        ]
    }

    async def slow_score(entity, research_result, user_id, entity_index, total_entities):
        await asyncio.sleep(sleep_seconds)
        from schemas.risk_result import RiskLevel, RiskResult

        return RiskResult(
            entity_id=entity.entity_id,
            entity_name=entity.name,
            entity_type=entity.entity_type,
            risk_level=RiskLevel.CLEAR,
            triggered_rule="test_rule",
            reasoning="test reasoning",
            research_confidence=research_result.confidence,
        )

    start = time.monotonic()
    with patch("orchestrator.score_entity_risk", side_effect=slow_score):
        scored = await run_risk_scoring(entity_results, user_id="parallel-test")

    elapsed = time.monotonic() - start
    sequential_estimate = sleep_seconds * 3

    if len(scored[EntityType.BUSINESS]) != 3:
        print("FAILED: expected 3 scored entities")
        return False

    if elapsed >= sequential_estimate * 0.75:
        print(
            f"FAILED: risk scoring appears sequential "
            f"(elapsed={elapsed:.2f}s, sequential≈{sequential_estimate:.2f}s)"
        )
        return False

    print(
        f"PASSED: risk scoring ran in parallel "
        f"(elapsed={elapsed:.2f}s vs sequential≈{sequential_estimate:.2f}s)"
    )
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Pipeline Parallel Execution")
    print("=" * 60 + "\n")

    ok = asyncio.run(test_specialists_run_in_parallel())
    ok = asyncio.run(test_risk_scoring_runs_in_parallel()) and ok

    print("\n" + "=" * 60)
    if ok:
        print("ALL TESTS PASSED")
        sys.exit(0)
    print("TESTS FAILED")
    sys.exit(1)
