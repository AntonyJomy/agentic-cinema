"""
tests/test_schema_precision.py

Tests for the precision improvement fields: depiction_context and ambiguity_reason.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from schemas.entities import Entity, EntityType, ScriptLocation, ExtractionMetadata, Entities
from schemas.risk_result import RiskLevel, RiskResult


def test_depiction_context_can_be_set():
    """Test that depiction_context can be explicitly set on an Entity."""
    entity = Entity(
        name="McDonald's",
        entity_type=EntityType.BUSINESS,
        context="The characters eat at McDonald's.",
        location=ScriptLocation(page_number=5, line_excerpt="McDonald's"),
        confidence=0.95,
        depiction_context="neutral",
        ambiguity_reason=None,
    )
    assert entity.depiction_context == "neutral"
    print("PASSED: depiction_context can be set to 'neutral'")


def test_depiction_context_positive():
    """Test positive portrayal depiction context."""
    entity = Entity(
        name="Local Hero Store",
        entity_type=EntityType.BUSINESS,
        context="The hero runs to Local Hero Store to save the day.",
        location=ScriptLocation(page_number=10, line_excerpt="Local Hero Store"),
        confidence=0.85,
        depiction_context="positive",
    )
    assert entity.depiction_context == "positive"
    print("PASSED: depiction_context can be set to 'positive'")


def test_depiction_context_negative():
    """Test negative portrayal depiction context."""
    entity = Entity(
        name="Criminal's Hideout",
        entity_type=EntityType.BUSINESS,
        context="The villains meet at Criminal's Hideout to plan the robbery.",
        location=ScriptLocation(page_number=15, line_excerpt="Criminal's Hideout"),
        confidence=0.8,
        depiction_context="negative",
    )
    assert entity.depiction_context == "negative"
    print("PASSED: depiction_context can be set to 'negative'")


def test_depiction_context_on_screen():
    """Test on-screen visual portrayal depiction context."""
    entity = Entity(
        name="Apple Logo",
        entity_type=EntityType.LOGO_BRAND,
        context="Close-up of an Apple logo on the laptop screen.",
        location=ScriptLocation(page_number=8, line_excerpt="Apple logo"),
        confidence=0.9,
        depiction_context="on-screen",
    )
    assert entity.depiction_context == "on-screen"
    print("PASSED: depiction_context can be set to 'on-screen'")


def test_depiction_context_suspicious():
    """Test suspicious portrayal depiction context."""
    entity = Entity(
        name="Unknown Corporation",
        entity_type=EntityType.BUSINESS,
        context="The protagonist receives documents from Unknown Corporation.",
        location=ScriptLocation(page_number=20, line_excerpt="Unknown Corporation"),
        confidence=0.6,
        depiction_context="suspicious",
    )
    assert entity.depiction_context == "suspicious"
    print("PASSED: depiction_context can be set to 'suspicious'")


def test_depiction_context_ambiguous():
    """Test ambiguous portrayal depiction context."""
    entity = Entity(
        name="The Office",
        entity_type=EntityType.BUSINESS,
        context="They go to The Office to discuss the merger.",
        location=ScriptLocation(page_number=12, line_excerpt="The Office"),
        confidence=0.5,
        depiction_context="ambiguous",
    )
    assert entity.depiction_context == "ambiguous"
    print("PASSED: depiction_context can be set to 'ambiguous'")


def test_depiction_context_default_is_none():
    """Test that depiction_context defaults to None when not set."""
    entity = Entity(
        name="Generic Store",
        entity_type=EntityType.BUSINESS,
        context="They buy something.",
        location=ScriptLocation(page_number=3, line_excerpt="Store"),
        confidence=0.7,
    )
    assert entity.depiction_context is None
    print("PASSED: depiction_context defaults to None")


def test_ambiguity_reason_can_be_set():
    """Test that ambiguity_reason can be explicitly set."""
    entity = Entity(
        name="Local Diner",
        entity_type=EntityType.BUSINESS,
        context="The characters go to a local diner.",
        location=ScriptLocation(page_number=7, line_excerpt="Local Diner"),
        confidence=0.6,
        ambiguity_reason="could be fictional or real common name",
    )
    assert entity.ambiguity_reason == "could be fictional or real common name"
    print("PASSED: ambiguity_reason can be set")


def test_ambiguity_reason_for_generic_terms():
    """Test ambiguity_reason for generic terms."""
    entity = Entity(
        name="Sunset Boulevard",
        entity_type=EntityType.ADDRESS,
        context="The car drives down Sunset Boulevard.",
        location=ScriptLocation(page_number=5, line_excerpt="Sunset Boulevard"),
        confidence=0.55,
        ambiguity_reason="unclear if this is a brand or generic term",
    )
    assert entity.ambiguity_reason == "unclear if this is a brand or generic term"
    print("PASSED: ambiguity_reason works for generic terms")


def test_ambiguity_reason_for_fictional_context():
    """Test ambiguity_reason for fictional context."""
    entity = Entity(
        name="John Smith",
        entity_type=EntityType.CHARACTER_NAME,
        context="John Smith is the protagonist of this story.",
        location=ScriptLocation(page_number=1, line_excerpt="John Smith"),
        confidence=0.45,
        ambiguity_reason="appears in a fictional context",
    )
    assert entity.ambiguity_reason == "appears in a fictional context"
    print("PASSED: ambiguity_reason works for fictional context")


def test_ambiguity_reason_none_when_high_confidence():
    """Test that ambiguity_reason is None when confidence is high."""
    entity = Entity(
        name="Coca-Cola",
        entity_type=EntityType.LOGO_BRAND,
        context="A clear Coca-Cola can is on the table.",
        location=ScriptLocation(page_number=4, line_excerpt="Coca-Cola"),
        confidence=0.95,
        ambiguity_reason=None,
    )
    assert entity.ambiguity_reason is None
    print("PASSED: ambiguity_reason is None for high-confidence entities")


def test_ambiguity_reason_none_when_high_confidence():
    """Test that ambiguity_reason is None when confidence is high."""
    entity = Entity(
        name="Coca-Cola",
        entity_type=EntityType.LOGO_BRAND,
        context="A clear Coca-Cola can is on the table.",
        location=ScriptLocation(page_number=4, line_excerpt="Coca-Cola"),
        confidence=0.95,
        ambiguity_reason=None,
    )
    assert entity.ambiguity_reason is None
    print("PASSED: ambiguity_reason is None for high-confidence entities")


def test_risk_result_trigger_rule_field():
    """Test that RiskResult has the triggered_rule field."""
    risk_result = RiskResult(
        entity_id="test-123",
        entity_name="McDonald's",
        entity_type=EntityType.BUSINESS,
        risk_level=RiskLevel.CLEAR,
        triggered_rule="clear_business_no_match",
        reasoning="No real-world match found in research.",
        evidence=[],
        research_confidence=0.95,
    )
    assert risk_result.triggered_rule == "clear_business_no_match"
    print("PASSED: RiskResult has triggered_rule field")


def test_risk_result_reasoning_field():
    """Test that RiskResult has the reasoning field."""
    risk_result = RiskResult(
        entity_id="test-123",
        entity_name="McDonald's",
        entity_type=EntityType.BUSINESS,
        risk_level=RiskLevel.CAUTION,
        triggered_rule="ambiguous_business_match",
        reasoning="Similar name found but not definitively matched.",
        evidence=[],
        research_confidence=0.7,
    )
    assert risk_result.reasoning == "ambiguous_business_match"
    print("PASSED: RiskResult has reasoning field")


def test_risk_result_evidence_field():
    """Test that RiskResult has the evidence field."""
    risk_result = RiskResult(
        entity_id="test-123",
        entity_name="Love Story",
        entity_type=EntityType.SONG,
        risk_level=RiskLevel.HIGH_RISK,
        triggered_rule="specific_song_identified",
        reasoning="Song clearly identified in screenplay.",
        evidence=[],
        research_confidence=0.98,
    )
    assert risk_result.evidence == []
    print("PASSED: RiskResult has evidence field")


def test_risk_result_research_confidence_field():
    """Test that RiskResult has the research_confidence field."""
    risk_result = RiskResult(
        entity_id="test-123",
        entity_name="Elon Musk",
        entity_type=EntityType.REAL_PUBLIC_FIGURE,
        risk_level=RiskLevel.HIGH_RISK,
        triggered_rule="real_person_identified",
        reasoning="Real person clearly referenced.",
        evidence=[],
        research_confidence=0.99,
    )
    assert risk_result.research_confidence == 0.99
    print("PASSED: RiskResult has research_confidence field")


def test_risk_result_requires_human_review_field():
    """Test that RiskResult has the requires_human_review field."""
    risk_result = RiskResult(
        entity_id="test-123",
        entity_name="Elon Musk",
        entity_type=EntityType.REAL_PUBLIC_FIGURE,
        risk_level=RiskLevel.HIGH_RISK,
        triggered_rule="real_person_identified",
        reasoning="Real person clearly referenced.",
        evidence=[],
        research_confidence=0.99,
        requires_human_review=True,
    )
    assert risk_result.requires_human_review is True
    print("PASSED: RiskResult has requires_human_review field")


def test_full_entity_with_precision_fields():
    """Test a complete Entity with all precision improvement fields."""
    entity = Entity(
        name="McDonald's",
        entity_type=EntityType.BUSINESS,
        context="The characters eat at McDonald's. It's a busy lunch rush.",
        location=ScriptLocation(page_number=5, scene_number=2, line_excerpt="McDonald's"),
        confidence=0.95,
        depiction_context="on-screen",
        ambiguity_reason=None,
    )
    
    assert entity.name == "McDonald's"
    assert entity.entity_type == EntityType.BUSINESS
    assert entity.depiction_context == "on-screen"
    assert entity.ambiguity_reason is None
    assert entity.risk_category is not None
    print("PASSED: Full Entity with precision fields works correctly")


def test_entities_with_multiple_depiction_contexts():
    """TestEntities object with multiple entities having different depiction contexts."""
    entities = Entities(
        run_id="test-run-123",
        script_id="test-script",
        script_title="Test Script",
        entities=[
            Entity(
                name="McDonald's",
                entity_type=EntityType.BUSINESS,
                context="Positively depicted as the hero's favorite place.",
                location=ScriptLocation(page_number=5, line_excerpt="McDonald's"),
                confidence=0.9,
                depiction_context="positive",
            ),
            Entity(
                name="Local Diner",
                entity_type=EntityType.BUSINESS,
                context="The villain meets his contact at the local diner.",
                location=ScriptLocation(page_number=10, line_excerpt="Local Diner"),
                confidence=0.65,
                depiction_context="negative",
                ambiguity_reason="could be fictional or real common name",
            ),
            Entity(
                name="General Store",
                entity_type=EntityType.BUSINESS,
                context="Neutral mention of a general store.",
                location=ScriptLocation(page_number=15, line_excerpt="General Store"),
                confidence=0.55,
                depiction_context="neutral",
                ambiguity_reason="unclear if this is a brand or generic term",
            ),
        ],
        metadata=ExtractionMetadata(
            model_used="gemini-3.6-flash",
            extracted_at=datetime.now(timezone.utc),
            extraction_agent_version="0.1.0",
            total_pages_scanned=20,
        ),
    )
    
    assert entities.entity_count == 3
    
    positive = [e for e in entities.entities if e.depiction_context == "positive"]
    negative = [e for e in entities.entities if e.depiction_context == "negative"]
    neutral = [e for e in entities.entities if e.depiction_context == "neutral"]
    ambiguous = [e for e in entities.entities if e.ambiguity_reason is not None]
    
    assert len(positive) == 1
    assert len(negative) == 1
    assert len(neutral) == 1
    assert len(ambiguous) == 2
    
    print("PASSED: Entities with multiple depiction contexts works correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Schema Precision Fields")
    print("=" * 60 + "\n")
    
    tests = [
        test_depiction_context_can_be_set,
        test_depiction_context_positive,
        test_depiction_context_negative,
        test_depiction_context_on_screen,
        test_depiction_context_suspicious,
        test_depiction_context_ambiguous,
        test_depiction_context_default_is_none,
        test_ambiguity_reason_can_be_set,
        test_ambiguity_reason_for_generic_terms,
        test_ambiguity_reason_for_fictional_context,
        test_ambiguity_reason_none_when_high_confidence,
        test_risk_result_trigger_rule_field,
        test_risk_result_reasoning_field,
        test_risk_result_evidence_field,
        test_risk_result_research_confidence_field,
        test_risk_result_requires_human_review_field,
        test_full_entity_with_precision_fields,
        test_entities_with_multiple_depiction_contexts,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(True)
        except Exception as e:
            print(f"FAILED: {test.__name__} - {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("ALL TESTS PASSED")
        sys.exit(0)
    print("TESTS FAILED")
    sys.exit(1)