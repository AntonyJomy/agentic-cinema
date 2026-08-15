"""
tests/test_edge_cases_extraction.py

Tests extraction agent precision with edge case screenplay.
"""
from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from schemas.entities import Entities
from gatekeeper.deterministic_grounding import ground_entities
import json


EDGE_CASES_SCRIPT = """
INT. THE DINER - DAY

A bustling roadside diner. The sign outside reads "DINER" in bold letters.

JACK (40s), a weary detective, sits at the counter.
MIKE (50s), the owner, wipes down the counter.

JACK
Another coffee, Mike. The usual.

MIKE
Coming right up, Jack.

REPORTER (V.O.)
The city council has approved the new zoning law despite opposition from local business owners.

EXT. MAIN STREET - DAY

A car drives past. The license plate reads "G7H-928".

A SIGN on the building reads "123 Main Street".

INT. BULLETIN OFFICE - DAY

JANE (30s), a reporter, sits at her desk.

EXT. PARK - DAY

A monument stands in the center of the park. The plaque reads:
"IN MEMORY OF GEORGE WASHINGTON"

INT. CONFERENCE ROOM - DAY

PRESIDENT SMITH enters the room. He's a real public figure.

PRESIDENT SMITH
Thank you all for being here.

INT. JEWELER'S STORE - DAY

Behind the counter, a display case holds watches.
A plaque reads "Authentic TIFANY & CO." (intentional misspelling).

EXT. ALLEYWAY - NIGHT

A shadowy figure approaches. The character wears a hoodie with
a logo: a swoosh symbol.

INT. APARTMENT - NIGHT

A TV plays. The sound is muffled, but we hear:

"AND I'M FALLING, FALLING... LANDSLIDE, LANDSLIDE..."

INT. OFFICE - DAY

PRESIDENT SMITH shakes hands with attendees.

PRESIDENT SMITH
We'll discuss this in the next meeting.

EXT. STREETS OF NEW YORK - DAY

A taxi drives by. The license plate reads "NYC-123".

A neon sign reads "BAR & GRILL" on the corner.

INT. THE BAR - NIGHT

JACK meets with a source. The bar sign reads "The Bar & Grill".

SOURCE
I heard you're looking for McDonald's.

JACK
McDonald's?

SOURCE
Yeah. The one on 5th.

EXT. STREET - NIGHT

A car speeds away. The license plate reads "ABC-456".

INT. CAFE - DAY

JESSICA sits by the window.

RADIO
(playing)
"And I'm falling, falling... Landslide, Landslide..."

INT. TRAIN STATION - DAY

A TRAIN departs. The destination board reads "ATLANTA".

INT. RESTAURANT - DAY

A menu is displayed. One item: "McDonald's Special Burger".

CLERK
Our signature item. Try it.

EXT. CEMETERY - DAY

A墓碑 reads "Here lies George Washington".

INT. ARCHIVES - DAY

A DOCUMENT is displayed:
"Application for McDonald's Franchise - 1985"

INT. THEATER - DAY

A MOVIE poster shows: "LOVE STORY - STARRING ROMEO AND JULIET"

INT. STUDIO - DAY

A TV SCREEN plays: "ELON MUSK INTERVIEW - LIVE NOW"

EXT. SKYLINE - DAY

A BILLBOARD reads: "ELON MUSK FOR PRESIDENT 2024"

INT. LIBRARY - DAY

A BOOK on the shelf: "The Life of Elon Musk" by Walter Isaacson.

INT. CLASSROOM - DAY

A TEACHER writes on the board:
"Elon Musk founded PayPal in 1999."

INT. INTERVIEW - DAY

REPORTER
Elon, what inspired you to start SpaceX?

ELON MUSK
I wanted to make life multi-planetary.

EXT. FARM - DAY

A CATTLE brand on a cow reads: "MCDONALDS FARM".

INT. OFFICE - DAY

A SIGN on the wall reads: "MCDONALD'S CONSULTING - BUSINESS SOLUTIONS".

EXT. CITY HALL - DAY

A CEREMONY takes place. PRESIDENT SMITH cuts a ribbon.

PRESIDENT SMITH
Today we open the new McDonald's Community Center.

INT. NEWSROOM - DAY

JANE reads the headlines:
"McDonald's Opens New Community Center"

EXT. PARK - DAY

A STATUE stands in the park. The base reads:
"GEORGE WASHINGTON - FIRST PRESIDENT"

INT. GYM - DAY

A WEIGHTLIFTER lifts a barbell. A logo on the weight is: "Nike".

INT. STORE - DAY

A SHELF holds products. One has a logo: "Apple".

A SIGN above reads: "Apple Store - Premium Electronics".

EXT. AIRPORT - DAY

A PLANE flies overhead. The tail has: "Delta Airlines".

INT. OFFICE - DAY

A COMPUTER screen shows: "Apple Inc. Stock Price: $150.00"

EXT. HIGHWAY - DAY

A TRUCK drives by. The side reads: "FedEx".

INT. WAREHOUSE - DAY

A PACKAGE is labeled: "FedEx - Express Delivery".

EXT. BUS STATION - DAY

A BUS pulls up. The side reads: "Greyhound".

INT. DINER - DAY

The same diner from the beginning.

EXT. STREET - DAY

A taxi drives by. License plate: "XYZ-789".
"""

GROUNDED_TEST_SCRIPT = """
INT. THE DINER - DAY

A bustling roadside diner. The sign outside reads "DINER" in bold letters.

JACK (40s), a weary detective, sits at the counter.
MIKE (50s), the owner, wipes down the counter.

EXT. MAIN STREET - DAY

A car drives past. The license plate reads "G7H-928".

A SIGN on the building reads "123 Main Street".

INT. JEWELER'S STORE - DAY

Behind the counter, a display case holds watches.
A plaque reads "Authentic TIFANY & CO." (intentional misspelling).

EXT. ALLEYWAY - NIGHT

A shadowy figure approaches. The character wears a hoodie with
a logo: a swoosh symbol.

INT. APARTMENT - NIGHT

A TV plays. The sound is muffled, but we hear:

"AND I'M FALLING, FALLING... LANDSLIDE, LANDSLIDE..."

EXT. STREETS OF NEW YORK - DAY

A taxi drives by. The license plate reads "NYC-123".

A neon sign reads "BAR & GRILL" on the corner.

INT. THE BAR - NIGHT

JACK meets with a source. The bar sign reads "The Bar & Grill".

SOURCE
I heard you're looking for McDonald's.

JACK
McDonald's?

SOURCE
Yeah. The one on 5th.

EXT. STREET - NIGHT

A car speeds away. The license plate reads "ABC-456".

INT. CAFE - DAY

JESSICA sits by the window.

RADIO
(playing)
"And I'm falling, falling... Landslide, Landslide..."

INT. RESTAURANT - DAY

A menu is displayed. One item: "McDonald's Special Burger".

CLERK
Our signature item. Try it.

INT. THEATER - DAY

A MOVIE poster shows: "LOVE STORY - STARRING ROMEO AND JULIET"

INT. STUDIO - DAY

A TV SCREEN plays: "ELON MUSK INTERVIEW - LIVE NOW"

EXT. SKYLINE - DAY

A BILLBOARD reads: "ELON MUSK FOR PRESIDENT 2024"

INT. LIBRARY - DAY

A BOOK on the shelf: "The Life of Elon Musk" by Walter Isaacson.

INT. CLASSROOM - DAY

A TEACHER writes on the board:
"Elon Musk founded PayPal in 1999."

INT. INTERVIEW - DAY

ELON MUSK
I wanted to make life multi-planetary.

EXT. FARM - DAY

A CATTLE brand on a cow reads: "MCDONALDS FARM".

INT. OFFICE - DAY

A SIGN on the wall reads: "MCDONALD'S CONSULTING - BUSINESS SOLUTIONS".

EXT. CITY HALL - DAY

A CEREMONY takes place. PRESIDENT SMITH cuts a ribbon.

PRESIDENT SMITH
Today we open the new McDonald's Community Center.

EXT. PARK - DAY

A STATUE stands in the park. The base reads:
"GEORGE WASHINGTON - FIRST PRESIDENT"

INT. GYM - DAY

A WEIGHTLIFTER lifts a barbell. A logo on the weight is: "Nike".

INT. STORE - DAY

A SHELF holds products. One has a logo: "Apple".

EXT. AIRPORT - DAY

A PLANE flies overhead. The tail has: "Delta Airlines".

INT. OFFICE - DAY

A COMPUTER screen shows: "Apple Inc. Stock Price: $150.00"

EXT. HIGHWAY - DAY

A TRUCK drives by. The side reads: "FedEx".

INT. WAREHOUSE - DAY

A PACKAGE is labeled: "FedEx - Express Delivery".

EXT. BUS STATION - DAY

A BUS pulls up. The side reads: "Greyhound".

INT. DINER - DAY

The same diner from the beginning.

EXT. STREET - DAY

A taxi drives by. License plate: "XYZ-789".
"""


def test_edge_case_entities():
    """Test that edge case entities can be parsed correctly."""
    from schemas.entities import Entity, EntityType, ScriptLocation, ExtractionMetadata
    
    entities_data = {
        "run_id": "test-run-edge-cases",
        "script_id": "edge_cases",
        "script_title": "Edge Cases Screenplay",
        "entities": [
            {
                "name": "McDonald's",
                "entity_type": "business",
                "context": "SOURCE says McDonald's is not a good idea.",
                "location": {"page_number": 10, "line_excerpt": "McDonald's"},
                "confidence": 0.65,
                "depiction_context": "suspicious",
                "ambiguity_reason": "could be fictional or real common name",
            },
            {
                "name": "Love Story",
                "entity_type": "song",
                "context": "Radio plays 'Love Story'.",
                "location": {"page_number": 12, "line_excerpt": "Love Story"},
                "confidence": 0.9,
                "depiction_context": "neutral",
                "ambiguity_reason": None,
            },
            {
                "name": "Elon Musk",
                "entity_type": "real_public_figure",
                "context": "Elon Musk founded PayPal in 1999.",
                "location": {"page_number": 20, "line_excerpt": "Elon Musk"},
                "confidence": 0.95,
                "depiction_context": "neutral",
                "ambiguity_reason": None,
                "requires_human_review": True,
            },
            {
                "name": "Nike",
                "entity_type": "logo_brand",
                "context": "Logo on weight is: Nike.",
                "location": {"page_number": 25, "line_excerpt": "Nike"},
                "confidence": 0.85,
                "depiction_context": "on-screen",
                "ambiguity_reason": None,
            },
            {
                "name": "Apple",
                "entity_type": "logo_brand",
                "context": "Logo on product: Apple.",
                "location": {"page_number": 26, "line_excerpt": "Apple"},
                "confidence": 0.92,
                "depiction_context": "on-screen",
                "ambiguity_reason": None,
            },
            {
                "name": "FedEx",
                "entity_type": "logo_brand",
                "context": "Truck side reads: FedEx.",
                "location": {"page_number": 27, "line_excerpt": "FedEx"},
                "confidence": 0.95,
                "depiction_context": "on-screen",
                "ambiguity_reason": None,
            },
            {
                "name": "TIFANY & CO.",
                "entity_type": "logo_brand",
                "context": "Plaque reads 'Authentic TIFANY & CO.'",
                "location": {"page_number": 8, "line_excerpt": "TIFANY & CO."},
                "confidence": 0.8,
                "depiction_context": "on-screen",
                "ambiguity_reason": "unclear if this is a brand or generic term",
            },
        ],
        "metadata": {
            "model_used": "gemini-3.6-flash",
            "extracted_at": "2024-01-01T00:00:00Z",
            "extraction_agent_version": "0.1.0",
            "total_pages_scanned": 10,
        },
    }
    
    entities = Entities.model_validate(entities_data)
    
    # Verify entities were parsed correctly
    assert entities.entity_count == 7
    
    # Verify depiction_context
    McDonalds = next(e for e in entities.entities if e.name == "McDonald's")
    assert McDonalds.depiction_context == "suspicious"
    assert McDonalds.ambiguity_reason == "could be fictional or real common name"
    
    LoveStory = next(e for e in entities.entities if e.name == "Love Story")
    assert LoveStory.depiction_context == "neutral"
    assert LoveStory.ambiguity_reason is None
    
    # Verify requires_human_review for real_public_figure
    ElonMusk = next(e for e in entities.entities if e.name == "Elon Musk")
    assert ElonMusk.requires_human_review is True
    
    print("PASSED: Edge case entities parsed correctly")


def test_grounding_with_edge_cases():
    """Test deterministic grounding with edge case entities."""
    from gatekeeper.deterministic_grounding import ground_entities
    from schemas.entities import Entity, EntityType, ScriptLocation, Entities, ExtractionMetadata
    
    test_entities = Entities(
        run_id="grounding-test",
        script_id="edge_cases",
        script_title="Edge Cases",
        entities=[
            Entity(
                name="McDonald's",
                entity_type=EntityType.BUSINESS,
                context="SOURCE says McDonald's is not a good idea.",
                location=ScriptLocation(page_number=10, line_excerpt="McDonald's"),
                confidence=0.65,
                depiction_context="suspicious",
            ),
            Entity(
                name="Love Story",
                entity_type=EntityType.SONG,
                context="Radio plays 'Love Story'.",
                location=ScriptLocation(page_number=12, line_excerpt="Love Story"),
                confidence=0.9,
            ),
            Entity(
                name="Elon Musk",
                entity_type=EntityType.REAL_PUBLIC_FIGURE,
                context="Elon Musk founded PayPal in 1999.",
                location=ScriptLocation(page_number=20, line_excerpt="Elon Musk"),
                confidence=0.95,
                requires_human_review=True,
            ),
            Entity(
                name="Nike",
                entity_type=EntityType.LOGO_BRAND,
                context="Logo on weight is: Nike.",
                location=ScriptLocation(page_number=25, line_excerpt="Nike"),
                confidence=0.85,
            ),
            Entity(
                name="Apple",
                entity_type=EntityType.LOGO_BRAND,
                context="Logo on product: Apple.",
                location=ScriptLocation(page_number=26, line_excerpt="Apple"),
                confidence=0.92,
            ),
            Entity(
                name="TIFANY & CO.",
                entity_type=EntityType.LOGO_BRAND,
                context="Plaque reads 'Authentic TIFANY & CO.'",
                location=ScriptLocation(page_number=8, line_excerpt="TIFANY & CO."),
                confidence=0.8,
            ),
        ],
        metadata=ExtractionMetadata(
            model_used="test",
            extracted_at=None,
            extraction_agent_version="0.1.0",
        ),
    )
    
    filtered, grounded, rejected = ground_entities(GROUNDED_TEST_SCRIPT, test_entities)
    
    print(f"Grounded: {len(grounded)} entities")
    for e in grounded:
        print(f"  - {e.name}")
    
    print(f"Rejected: {len(rejected)} entities")
    for e in rejected:
        print(f"  - {e.name}")
    
    # Most entities should be grounded
    assert len(grounded) >= 5, f"Expected at least 5 grounded entities, got {len(grounded)}"
    
    # Verify preserved fields
    for g in grounded:
        if g.name == "Elon Musk":
            assert g.requires_human_review is True
            print(f"PASSED: Elon Musk requires_human_review preserved")
    
    print("PASSED: Grounding works with edge cases")


def test_edge_case_extraction_output():
    """Test parsing extraction agent output with edge cases."""
    # Simulate extraction agent output with edge cases
    extraction_output = {
        "run_id": "extraction-edge-cases",
        "script_id": "edge_cases",
        "script_title": "Edge Cases Screenplay",
        "entities": [
            {
                "name": "McDonald's",
                "entity_type": "business",
                "context": "SOURCE says McDonald's is not a good idea.",
                "location": {"page_number": 10, "line_excerpt": "McDonald's"},
                "confidence": 0.65,
                "depiction_context": "suspicious",
                "ambiguity_reason": "could be fictional or real common name",
            },
            {
                "name": "Elon Musk",
                "entity_type": "real_public_figure",
                "context": "Elon Musk founded PayPal in 1999.",
                "location": {"page_number": 20, "line_excerpt": "Elon Musk"},
                "confidence": 0.95,
                "depiction_context": "neutral",
                "ambiguity_reason": None,
                "requires_human_review": True,
            },
            {
                "name": "TIFANY & CO.",
                "entity_type": "logo_brand",
                "context": "Plaque reads 'Authentic TIFANY & CO.'",
                "location": {"page_number": 8, "line_excerpt": "TIFANY & CO."},
                "confidence": 0.8,
                "depiction_context": "on-screen",
                "ambiguity_reason": "unclear if this is a brand or generic term",
            },
            {
                "name": "Nike",
                "entity_type": "logo_brand",
                "context": "Logo on weight is: Nike.",
                "location": {"page_number": 25, "line_excerpt": "Nike"},
                "confidence": 0.85,
                "depiction_context": "on-screen",
                "ambiguity_reason": None,
            },
            {
                "name": "Apple",
                "entity_type": "logo_brand",
                "context": "Logo on product: Apple.",
                "location": {"page_number": 26, "line_excerpt": "Apple"},
                "confidence": 0.92,
                "depiction_context": "on-screen",
                "ambiguity_reason": None,
            },
        ],
        "metadata": {
            "model_used": "gemini-3.6-flash",
            "extracted_at": "2024-01-01T00:00:00Z",
            "extraction_agent_version": "0.1.0",
            "total_pages_scanned": 10,
        },
    }
    
    entities = Entities.model_validate(extraction_output)
    
    # Verify depiction_context
    assert entities.entities[0].depiction_context == "suspicious"
    assert entities.entities[0].ambiguity_reason == "could be fictional or real common name"
    assert entities.entities[1].requires_human_review is True
    
    print("PASSED: Edge case extraction output parsed correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Edge Case Extraction")
    print("=" * 60 + "\n")
    
    tests = [
        test_edge_case_entities,
        test_grounding_with_edge_cases,
        test_edge_case_extraction_output,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(True)
        except Exception as e:
            print(f"FAILED: {test.__name__} - {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("ALL TESTS PASSED")
        sys.exit(0)
    print("TESTS FAILED")
    sys.exit(1)