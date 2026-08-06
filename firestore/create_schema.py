from google.cloud import firestore
import uuid
from datetime import datetime, timezone

db = firestore.Client(project="script-clearance-hackathon", database="script-clearance-db")

run_id = str(uuid.uuid4())
entity_1_id = str(uuid.uuid4())
entity_2_id = str(uuid.uuid4())

entities = [
    {
        "entity_id": entity_1_id,
        "name": "Sunny's Bar",
        "entity_type": "business",
        "risk_category": "business_location",
        "context": "A dive bar in downtown Atlanta.",
        "location": {
            "page_number": 12,
            "scene_number": 4,
            "line_excerpt": "INT. SUNNY'S BAR - NIGHT."
        },
        "confidence": 0.9,
        "requires_human_review": False,
        "extraction_notes": None,
        "evidence": [],
        "status": "flagged"
    },
    {
        "entity_id": entity_2_id,
        "name": "Landslide",
        "entity_type": "song",
        "risk_category": "music_rights",
        "context": "Plays on the radio in the background.",
        "location": {
            "page_number": 14,
            "scene_number": None,
            "line_excerpt": "Radio plays 'Landslide'"
        },
        "confidence": 0.85,
        "requires_human_review": False,
        "extraction_notes": None,
        "evidence": [],
        "status": "flagged"
    }
]

metadata = {
    "model_used": "gemini-2.5-flash",
    "extracted_at": datetime.now(timezone.utc).isoformat(),
    "extraction_agent_version": "0.1.0",
    "total_pages_scanned": 20
}

doc_ref = db.collection("clearance_runs").document(run_id)
doc_ref.set({
    "run_id": run_id,
    "script_id": "test_script_01",
    "script_title": "Test Script",
    "created_at": firestore.SERVER_TIMESTAMP,
    "updated_at": firestore.SERVER_TIMESTAMP,
    "overall_status": "flagged",
    "reviewed_by": None,
    "reviewed_at": None,
    "entities": entities,
    "metadata": metadata
})

print(f"✅ Schema document created with run_id: {run_id}")

# Read it back to confirm
doc = doc_ref.get()
print("✅ Confirmed contents:")
print(doc.to_dict())