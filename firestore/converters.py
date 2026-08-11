"""
firestore/converters.py

Bridges the Pydantic `Entity` model (schemas/entities.py) and the
Firestore-safe dict representation stored inside a clearance_run document.

The Pydantic model in schemas/entities.py is the single source of truth
for shape and validation. These two functions are the ONLY place that
shape should be translated to/from what Firestore actually stores — the
pipeline and gatekeeper call these, not model_dump()/Entity(**data)
directly, so there's exactly one place to fix if the mapping ever changes.
"""

from schemas.entities import Entity


def entity_to_firestore_dict(entity: Entity) -> dict:
    """
    Convert a validated Entity into a Firestore-safe dict.

    mode="json" is required (not the default mode) so every value is a
    Firestore/JSON-safe primitive:
      - Enums (entity_type, risk_category) become their plain string value,
        e.g. RiskCategory.MUSIC_RIGHTS -> "music_rights"
      - Nested models (location) become nested plain dicts
      - No Python-only objects leak into Firestore, which would otherwise
        fail to serialize or come back unusable on read.
    """
    return entity.model_dump(mode="json")


def firestore_dict_to_entity(data: dict) -> Entity:
    """
    Rebuild a validated Entity from a dict read back out of Firestore.

    Uses Entity.model_validate() (Pydantic's own validation path) rather
    than blind dict-unpacking (Entity(**data)), so if a document is ever
    malformed, partially written, or from an older schema version, this
    fails loudly and clearly right here — not silently somewhere downstream
    in the gatekeeper or frontend.
    """
    return Entity.model_validate(data)