"""
schemas/entities.py
This file defines the SHAPE OF DATA that flows through the entire
script clearance pipeline. It is the contract every agent builds against:
    Extraction agent  -->  produces an `Entities` object
    Grounding-check    -->  reads & filters an `Entities` object
    Orchestrator       -->  reads `entity.risk_category` to route work
    Specialist agents  -->  each receives ONE `Entity` object
    Scoring agent      -->  reads `Entity` + specialist findings
    Frontend           -->  displays these fields directly
    Firestore          -->  stores these objects inside a clearance run
Nothing downstream should invent its own shape for "an entity" —
everyone reads and writes THIS shape.
"""
from pydantic import BaseModel, Field, field_validator, model_validator

from enum import Enum

from datetime import datetime

from uuid import uuid4

# ---------------------------------------------------------------------------

# 1. WHAT KINDS OF THINGS ARE WE LOOKING FOR?

# ---------------------------------------------------------------------------

# This is the fixed list of "things worth flagging" in a screenplay.

# Using an Enum (not a plain string) means the extraction agent can ONLY

# pick from this list — it can't invent a new category on the fly.

class EntityType(str, Enum):

    BUSINESS = "business"                              # e.g. "Sunny's Bar"

    CHARACTER_NAME = "character_name"                   # might match a real person

    SONG = "song"                                       # music referenced/played

    LOGO_BRAND = "logo_brand"                           # visible brand/logo

    ADDRESS = "address"                                 # real-looking street address

    PHONE_NUMBER = "phone_number"                       # a phone number said/shown

    LICENSE_PLATE = "license_plate"                     # a vehicle plate shown

    QUOTE_OR_LITERARY_REFERENCE = "quote_or_literary_reference"

    REAL_PUBLIC_FIGURE = "real_public_figure"           # a real, named person

# ---------------------------------------------------------------------------

# 2. WHICH SPECIALIST SHOULD RESEARCH THIS?

# ---------------------------------------------------------------------------

# Each entity type needs a DIFFERENT kind of research. A business name and

# a song need completely different questions asked of Parallel. This enum

# is the label for "which specialist owns this."

class RiskCategory(str, Enum):

    BUSINESS_LOCATION = "business_location"

    NAME_COLLISION = "name_collision"

    MUSIC_RIGHTS = "music_rights"

    TRADEMARK_BRAND = "trademark_brand"

    PII_EXPOSURE = "pii_exposure"

    LITERARY_RIGHTS = "literary_rights"

    DEFAMATION_RISK = "defamation_risk"

# This dictionary is the SINGLE SOURCE OF TRUTH for routing.

# The orchestrator uses this — not scattered if/else logic — to decide

# which specialist gets which entity. That's what makes routing

# "explainable": anyone can open this file and see the exact rule.

ENTITY_TO_RISK_CATEGORY: dict[EntityType, RiskCategory] = {

    EntityType.BUSINESS: RiskCategory.BUSINESS_LOCATION,

    EntityType.CHARACTER_NAME: RiskCategory.NAME_COLLISION,

    EntityType.SONG: RiskCategory.MUSIC_RIGHTS,

    EntityType.LOGO_BRAND: RiskCategory.TRADEMARK_BRAND,

    EntityType.ADDRESS: RiskCategory.PII_EXPOSURE,

    EntityType.PHONE_NUMBER: RiskCategory.PII_EXPOSURE,

    EntityType.LICENSE_PLATE: RiskCategory.PII_EXPOSURE,

    EntityType.QUOTE_OR_LITERARY_REFERENCE: RiskCategory.LITERARY_RIGHTS,

    EntityType.REAL_PUBLIC_FIGURE: RiskCategory.DEFAMATION_RISK,

}

# ---------------------------------------------------------------------------

# 3. WHERE, EXACTLY, DID WE FIND THIS IN THE SCRIPT?

# ---------------------------------------------------------------------------

# A human reviewer (Ben, playing "Legal") needs to be able to find the

# exact line in the script that triggered a flag — not just "somewhere

# on page 12." This small model holds that precise location.

class ScriptLocation(BaseModel):

    page_number: int | None = Field(None, ge=1)

    scene_number: int | None = Field(None, ge=1)

    line_excerpt: str = Field(..., description="The exact line(s) the entity appeared in")

# ---------------------------------------------------------------------------

# 4. ONE SINGLE FLAGGED ENTITY

# ---------------------------------------------------------------------------

# This is the core object. Every specialist agent receives ONE of these

# as its input, and every finding in the final report traces back to one

# of these by its entity_id.

class Entity(BaseModel):

    entity_id: str = Field(default_factory=lambda: str(uuid4()))

    name: str = Field(..., min_length=1, description="Literal text found, e.g. 'Sunny's Bar'")

    entity_type: EntityType

    risk_category: RiskCategory = Field(

        default=None,

        description="Auto-filled from entity_type — see the validator below"

    )

    context: str = Field(..., min_length=1, description="Surrounding scene/dialogue context")

    location: ScriptLocation

    confidence: float = Field(

        ..., ge=0.0, le=1.0,

        description=(

            "EXTRACTION confidence only — how sure the extraction agent is "

            "that this is a real, checkable entity. This is NOT the same as "

            "evidence confidence (that comes later, from the specialist's "

            "research, and lives on a separate object). Keeping these two "

            "numbers apart is deliberate — see the note at the bottom of "

            "this file."

        ),

    )

    requires_human_review: bool = Field(

        default=False,

        description="Forced true for high-sensitivity types regardless of confidence"

    )

    extraction_notes: str | None = Field(

        None, description="Agent's brief reasoning for why this was flagged"

    )

    # PRECISION FIELDS for better filtering and prioritization
    depiction_context: str | None = Field(
        None,
        description=(
            "How the entity is portrayed in the script - neutral, positive, negative, or suspicious. "
            "Examples: 'named positively as a hero', 'mentioned in a criminal context', "
            "'showing as logo on screen', 'referenced negatively'. This helps prioritize risks."
        ),
    )
    ambiguity_reason: str | None = Field(
        None,
        description=(
            "Why the agent is uncertain about this entity. If present with low confidence (<0.7), "
            "this item can be shown separately from firm flags. Examples: "
            "'could be fictional or real common name', 'unclear if this is a brand or generic term'."
        ),
    )

    # --- Model validator: runs AFTER all fields are set, every single time,

    # regardless of whether a value was explicitly passed in or left as a

    # default. This is deliberately a model_validator (not field_validator)

    # because in Pydantic v2, field validators with defaults are SKIPPED

    # when the field isn't explicitly provided — a subtlety worth knowing,

    # since it silently breaks "auto-fill" logic if you don't account for it.

    @model_validator(mode="after")

    def apply_derived_fields(self) -> "Entity":

        """

        1. If risk_category wasn't explicitly set, derive it from entity_type

           using the routing map above. The extraction agent never has to

           think about routing — it just says "this is a BUSINESS" and the

           correct risk_category follows for free.

        2. Some entity types are sensitive enough that we NEVER want to

           silently auto-clear them, even if confidence is low — a real

           public figure mention always forces human review, no exceptions.

        """

        if self.risk_category is None:

            self.risk_category = ENTITY_TO_RISK_CATEGORY.get(self.entity_type)

        if self.entity_type == EntityType.REAL_PUBLIC_FIGURE:

            self.requires_human_review = True

        return self

# ---------------------------------------------------------------------------

# 5. INFORMATION ABOUT THE EXTRACTION RUN ITSELF

# ---------------------------------------------------------------------------

# This is what makes a run REPRODUCIBLE and AUDITABLE — you can always

# answer "which model version produced this, and when?"

class ExtractionMetadata(BaseModel):

    model_used: str = Field(..., description="e.g. 'gemini-2.5-flash'")

    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    extraction_agent_version: str = Field(default="0.1.0")

    total_pages_scanned: int | None = None

# ---------------------------------------------------------------------------

# 6. THE FULL OUTPUT OF ONE EXTRACTION RUN

# ---------------------------------------------------------------------------

# This is literally what the extraction agent returns, and what every

# downstream stage (grounding-check, specialists, scoring, frontend,

# Firestore) reads as its starting point.

class Entities(BaseModel):

    run_id: str = Field(default_factory=lambda: str(uuid4()))

    script_id: str

    script_title: str | None = None

    entities: list[Entity]

    metadata: ExtractionMetadata

    @property

    def entity_count(self) -> int:

        return len(self.entities)

    def entities_by_risk_category(self, category: RiskCategory) -> list[Entity]:

        """

        Helper used by the orchestrator: 'give me every entity that

        should go to the business_location specialist', etc.

        """

        return [e for e in self.entities if e.risk_category == category]
