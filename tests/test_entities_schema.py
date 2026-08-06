import sys
import os

# Add the project root to the path (works whether running from root or tests/)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from schemas.entities import Entities, Entity, EntityType, ScriptLocation, ExtractionMetadata, RiskCategory

def test_basic_entity_creation():

    """A normal business entity — risk_category should auto-derive."""

    e = Entity(

        name="Sunny's Bar",

        entity_type=EntityType.BUSINESS,

        context="INT. SUNNY'S BAR - NIGHT. A dive bar in downtown Atlanta.",

        location=ScriptLocation(page_number=12, scene_number=4, line_excerpt="INT. SUNNY'S BAR - NIGHT."),

        confidence=0.9,

    )

    assert e.risk_category == RiskCategory.BUSINESS_LOCATION, "risk_category should auto-derive from entity_type"

    print("PASS: business entity auto-routes to BUSINESS_LOCATION")

def test_sensitive_type_forces_review():

    """A real public figure mention should ALWAYS require human review,

    even if we don't explicitly set requires_human_review."""

    e = Entity(

        name="a real senator's name",

        entity_type=EntityType.REAL_PUBLIC_FIGURE,

        context="Dialogue references a real politician by name.",

        location=ScriptLocation(page_number=5, line_excerpt="mentions the senator directly"),

        confidence=0.6,

    )

    assert e.requires_human_review is True, "public figure mentions must force human review"

    print("PASS: real_public_figure forces requires_human_review=True")

def test_full_extraction_output():

    """The full Entities object, as the extraction agent would produce it."""

    entities = Entities(

        script_id="test_script_01",

        script_title="Test Script",

        entities=[

            Entity(

                name="Sunny's Bar",

                entity_type=EntityType.BUSINESS,

                context="A dive bar in downtown Atlanta.",

                location=ScriptLocation(page_number=12, scene_number=4, line_excerpt="INT. SUNNY'S BAR - NIGHT."),

                confidence=0.9,

            ),

            Entity(

                name="Landslide",

                entity_type=EntityType.SONG,

                context="Plays on the radio in the background.",

                location=ScriptLocation(page_number=14, line_excerpt="Radio plays 'Landslide'"),

                confidence=0.85,

            ),

        ],

        metadata=ExtractionMetadata(model_used="gemini-2.5-flash", total_pages_scanned=20),

    )

    assert entities.entity_count == 2

    business_only = entities.entities_by_risk_category(RiskCategory.BUSINESS_LOCATION)

    assert len(business_only) == 1

    assert business_only[0].name == "Sunny's Bar"

    print("PASS: full Entities object works, filtering by risk_category works")

    print("\n--- Example JSON output (this is what downstream agents receive) ---\n")

    print(entities.model_dump_json(indent=2))

if __name__ == "__main__":

    test_basic_entity_creation()

    test_sensitive_type_forces_review()

    test_full_extraction_output()

    print("\nAll tests passed. schemas/entities.py is ready to share with the team.")
