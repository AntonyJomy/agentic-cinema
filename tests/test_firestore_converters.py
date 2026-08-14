"""
Round-trip test: an Entity is created, converted to a Firestore-safe dict,
written to Firestore, read back, converted back into an Entity, and
compared field-by-field against the original.

Run directly: python tests/test_firestore_converters.py
"""
import sys
import os

# Ensure the repo root is importable regardless of where this is run from
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google.cloud import firestore

from schemas.entities import Entity, EntityType, ScriptLocation
from firestore.converters import entity_to_firestore_dict, firestore_dict_to_entity

db = firestore.Client(project="script-clearance-hackathon", database="script-clearance-db")
TEST_COLLECTION = "converter_roundtrip_tests"

# --- Case 1: a straightforward entity ---
original = Entity(
    name="Sunny's Bar",
    entity_type=EntityType.BUSINESS,
    context="A dive bar in downtown Atlanta.",
    location=ScriptLocation(page_number=12, scene_number=4, line_excerpt="INT. SUNNY'S BAR - NIGHT."),
    confidence=0.9,
    extraction_notes=None,
)

doc_ref = db.collection(TEST_COLLECTION).document(original.entity_id)
doc_ref.set(entity_to_firestore_dict(original))

fetched = doc_ref.get().to_dict()
rebuilt = firestore_dict_to_entity(fetched)

assert rebuilt == original, f"Round trip mismatch:\n  original={original}\n  rebuilt={rebuilt}"
print("PASS: basic entity round-trips identically through Firestore")

assert rebuilt.risk_category.value == "business_location"
print("PASS: auto-derived risk_category survives the round trip")

# --- Case 2: the forced-human-review edge case ---
sensitive = Entity(
    name="Senator Jane Whitfield",
    entity_type=EntityType.REAL_PUBLIC_FIGURE,
    context="Mentioned in a news broadcast overheard in the background.",
    location=ScriptLocation(page_number=44, scene_number=None, line_excerpt="RADIO: '...Senator Jane Whitfield today announced...'"),
    confidence=0.72,
)

assert sensitive.requires_human_review is True  # confirms the validator itself fired

doc_ref_2 = db.collection(TEST_COLLECTION).document(sensitive.entity_id)
doc_ref_2.set(entity_to_firestore_dict(sensitive))

fetched_2 = doc_ref_2.get().to_dict()
rebuilt_2 = firestore_dict_to_entity(fetched_2)

assert rebuilt_2 == sensitive
assert rebuilt_2.requires_human_review is True
print("PASS: forced requires_human_review=True for REAL_PUBLIC_FIGURE survives the round trip")

# --- Cleanup: keep the test collection from accumulating junk on every run ---
doc_ref.delete()
doc_ref_2.delete()

print("\nAll tests passed. firestore/converters.py is ready to share with the team.")