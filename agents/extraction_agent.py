"""
agents/extraction_agent.py

The Extraction Agent is the entry point of the script clearance pipeline.
It reads raw screenplay text and produces an `Entities` object containing
all flagged entities (business names, character names, songs, brands, etc.)

This agent produces the structured output that every downstream component
(extraction agent, grounding-check, orchestrator, specialists, scoring,
frontend, Firestore) consumes as its starting point.
"""
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from schemas.entities import Entities

# Load environment variables from .env file
load_dotenv()

# Create the extraction agent
extractor = LlmAgent(
    model="gemini-3.6-flash",
    name="extractor",
    description="Extracts flagged entities from screenplays for legal clearance review.",
    instruction="""
You are the Extraction Agent for a film script clearance system. Your job is to read a screenplay and identify EVERY instance of potentially problematic entities that need legal review.

You must find and flag:
- **Business names**: Real or fictional businesses (e.g., "Sunny's Bar", "McDonald's", "XYZ Corp")
- **Character names**: Names that might match real people (especially public figures)
- **Songs**: Music titles referenced or played in a scene
- **Logos/brands**: Visible logos, brand names, trademarks
- **Addresses**: Real street addresses or locations
- **Phone numbers**: Phone numbers shown or said
- **License plates**: Vehicle license plate numbers
- **Quotes/literary references**: Famous quotes, book titles, poem references
- **Real public figures**: Named real people (politicians, celebrities, historical figures)

For EACH entity you find, you MUST return:
1. `name`: The exact text as it appears in the script
2. `entity_type`: One of the EntityType enum values (business, character_name, song, logo_brand, address, phone_number, license_plate, quote_or_literary_reference, real_public_figure)
3. `context`: The surrounding scene/dialogue context (2-3 sentences before and after)
4. `location`: A ScriptLocation object with:
   - `page_number`: The page number where this appears (if determinable)
   - `scene_number`: The scene number (if determinable)
   - `line_excerpt`: The exact line(s) containing the entity
5. `confidence`: A float from 0.0 to 1.0 indicating how sure you are this is a real, checkable entity

IMPORTANT: 
- Do NOT set `risk_category` or `requires_human_review` — those are auto-derived by the schema validators
- Include EVERY instance you find, don't filter or summarize
- Be conservative — when in doubt, flag it
- The `context` field must include enough surrounding text for a human reviewer to understand the usage
""",
    output_schema=Entities,
)
