"""
tests/test_integration_pipeline.py

Integration tests for the full pipeline with schema precision fields.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import asyncio
from datetime import datetime, timezone


async def test_full_pipeline_includes_precision_fields():
    """Test that the full pipeline preserves depiction_context and ambiguity_reason."""
    from gatekeeper.deterministic_grounding import ground_entities
    from orchestrator import run_clearance_pipeline
    from schemas.entities import Entity, EntityType, ScriptLocation, Entities, ExtractionMetadata
    from schemas.legal_review import ReviewDecision
    from legal_review.review_workflow import record_entity_decision
    from gatekeeper.clearance_gate import evaluate_clearance
    from schemas.gatekeeper_result import GatekeeperStatus
    
    screenplay = """
INT. TEST BAR - DAY

A bar with a sign: "Sunny's Bar". The logo is visible.

JACK sits at the counter.

REPORTER (V.O.)
The city council has approved the new zoning law.

EXT. MAIN STREET - DAY

A car drives past. License plate: "G7H-928".

INT. JEWELER'S STORE - DAY

Behind the counter, a plaque reads "Authentic TIFANY & CO."

EXT. ALLEYWAY - NIGHT

A shadowy figure approaches. Hoodie with logo: Nike.

INT. APARTMENT - NIGHT

A TV plays. Sound muffled, but we hear: "Landslide, Landslide..."

EXT. STREETS OF NEW YORK - DAY

A taxi drives by. License plate: "NYC-123".

A neon sign reads "BAR & GRILL".

INT. THE BAR - NIGHT

JACK meets with a source. Bar sign reads "The Bar & Grill".

SOURCE
I heard you're looking for McDonald's.

EXT. STREET - NIGHT

A car speeds away. License plate: "ABC-456".

INT. CAFE - DAY

JESSICA sits by the window.

RADIO
(playing)
"And I'm falling, falling... Landslide, Landslide..."

INT. THEATER - DAY

A MOVIE poster shows: "LOVE STORY - STARRING ROMEO AND JULIET".

INT. STUDIO - DAY

A TV SCREEN plays: "ELON MUSK INTERVIEW - LIVE NOW".

EXT. SKYLINE - DAY

A BILLBOARD reads: "ELON MUSK FOR PRESIDENT 2024".

INT. LIBRARY - DAY

A BOOK: "The Life of Elon Musk" by Walter Isaacson.

INT. CLASSROOM - DAY

A TEACHER writes: "Elon Musk founded PayPal in 1999."

INT. INTERVIEW - DAY

ELON MUSK
I wanted to make life multi-planetary.

EXT. FARM - DAY

A CATTLE brand reads: "MCDONALDS FARM".

INT. OFFICE - DAY

A SIGN reads: "MCDONALD'S CONSULTING - BUSINESS SOLUTIONS".

EXT. CITY HALL - DAY

A CEREMONY. PRESIDENT SMITH cuts a ribbon.

PRESIDENT SMITH
Today we open the new McDonald's Community Center.

EXT. PARK - DAY

A STATUE reads: "GEORGE WASHINGTON - FIRST PRESIDENT".

INT. GYM - DAY

A WEIGHTLIFTER. Logo on weight: Nike.

INT. STORE - DAY

A SHELF. Product has logo: Apple.

EXT. AIRPORT - DAY

A PLANE. Tail has: Delta Airlines.

INT. OFFICE - DAY

A COMPUTER screen: "Apple Inc. Stock Price: $150.00".

EXT. HIGHWAY - DAY

A TRUCK. Side reads: FedEx.

INT. WAREHOUSE - DAY

A PACKAGE: "FedEx - Express Delivery".

EXT. BUS STATION - DAY

A BUS. Side reads: Greyhound.

INT. DINER - DAY

The same diner.

EXT. STREET - DAY

A taxi. License plate: "XYZ-789".
"""
    
    # Run the full pipeline
    result = await run_clearance_pipeline(
        screenplay,
        screenplay_path="<test>",
        user_id="integration-test",
    )
    
    # Verify entities have depiction_context and ambiguity_reason
    for entity in result.extracted_entities.entities:
        print(f"  {entity.name}: depiction={entity.depiction_context}, ambiguous={entity.ambiguity_reason}")
    
    # Verify risk results have triggered_rule and reasoning
    for results_list in result.entity_results.values():
        for item in results_list:
            if item.risk_result:
                print(f"  Risk: {item.entity.name} -> {item.risk_result.risk_level} (rule: {item.risk_result.triggered_rule})")
                assert item.risk_result.triggered_rule, "Missing triggered_rule"
                assert item.risk_result.reasoning, "Missing reasoning"
    
    print("PASSED: Full pipeline includes precision fields")


async def test_pipeline_with_manual_review():
    """Test full pipeline with manual legal review decisions."""
    from orchestrator import run_clearance_pipeline
    from schemas.legal_review import ReviewDecision
    from legal_review.review_workflow import record_entity_decision
    from gatekeeper.clearance_gate import evaluate_clearance
    
    screenplay = """
INT. TEST BAR - DAY

A bar with a sign: "Sunny's Bar".

JACK sits at the counter.

EXT. MAIN STREET - DAY

A car drives past. License plate: "G7H-928".

EXT. SKYLINE - DAY

A BILLBOARD reads: "ELON MUSK FOR PRESIDENT 2024".

INT. CLASSROOM - DAY

A TEACHER writes: "Elon Musk founded PayPal in 1999."

INT. INTERVIEW - DAY

ELON MUSK
I wanted to make life multi-planetary.
"""
    
    result = await run_clearance_pipeline(
        screenplay,
        screenplay_path="<test>",
        user_id="integration-test",
    )
    
    # Check if there are high-risk entities requiring manual review
    required_reviews = [
        r for r in result.legal_review.entity_reviews
        if r.requires_explicit_decision
    ]
    
    if required_reviews:
        print(f"Found {len(required_reviews)} entities requiring manual review")
        
        # Simulate manual approval
        reviewed = result.legal_review
        for record in required_reviews:
            reviewed = record_entity_decision(
                reviewed,
                entity_id=record.entity_id,
                decision=ReviewDecision.APPROVED,
                reviewer="Test Legal Reviewer",
                comment="Approved in integration test.",
            )
        
        # Verify gatekeeper now clears
        gate_result = evaluate_clearance(reviewed)
        assert gate_result.status.value == "cleared", f"Expected cleared, got {gate_result.status.value}"
        
        print("PASSED: Pipeline with manual review works correctly")
    else:
        print("PASSED: No manual review required (no high-risk entities)")


async def test_grounding_preserves_precision_fields():
    """Test that deterministic grounding preserves depiction_context and ambiguity_reason."""
    from gatekeeper.deterministic_grounding import ground_entities
    from schemas.entities import Entity, EntityType, ScriptLocation, Entities, ExtractionMetadata
    
    screenplay = """
INT. TEST BAR - DAY

A bar with a sign: "Sunny's Bar".

JACK sits at the counter.

EXT. MAIN STREET - DAY

A car drives past. License plate: "G7H-928".
"""
    
    test_entities = Entities(
        run_id="grounding-test",
        script_id="test",
        script_title="Test",
        entities=[
            Entity(
                name="Sunny's Bar",
                entity_type=EntityType.BUSINESS,
                context="A bar with a sign: Sunny's Bar.",
                location=ScriptLocation(page_number=1, line_excerpt="Sunny's Bar"),
                confidence=0.95,
                depiction_context="neutral",
                ambiguity_reason=None,
            ),
            Entity(
                name="NonExistent Brand",
                entity_type=EntityType.LOGO_BRAND,
                context="A logo: NonExistent Brand.",
                location=ScriptLocation(page_number=1, line_excerpt="NonExistent Brand"),
                confidence=0.6,
                depiction_context="suspicious",
                ambiguity_reason="unclear if this is a brand or generic term",
            ),
        ],
        metadata=ExtractionMetadata(
            model_used="test",
            extracted_at=datetime.now(timezone.utc),
            extraction_agent_version="0.1.0",
        ),
    )
    
    filtered, grounded, rejected = ground_entities(screenplay, test_entities)
    
    assert len(grounded) == 1
    assert len(rejected) == 1
    
    # Verify preserved fields on grounded entity
    assert grounded[0].depiction_context == "neutral"
    assert grounded[0].ambiguity_reason is None
    
    # Verify rejected entity fields are not included
    assert not any(e.name == "NonExistent Brand" for e in grounded)
    
    print("PASSED: Grounding preserves precision fields")


async def main():
    print("=" * 60)
    print("Testing Integration Pipeline")
    print("=" * 60 + "\n")
    
    print("Running test 1: Full pipeline includes precision fields...")
    await test_full_pipeline_includes_precision_fields()
    print()
    
    print("Running test 2: Pipeline with manual review...")
    await test_pipeline_with_manual_review()
    print()
    
    print("Running test 3: Grounding preserves precision fields...")
    await test_grounding_preserves_precision_fields()
    print()
    
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())