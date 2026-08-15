"""
tests/validate_extraction.py

Validates the extraction agent output against expected entities from the screenplay.
"""
import os
import sys
import json
import asyncio
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))
sys.path.insert(0, project_root)

import fitz  # PyMuPDF
from agents import extraction_agent
from schemas.entities import Entities
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Expected entities based on manual review of the first 2 pages of Screenplay_1.pdf
EXPECTED_ENTITIES = [
    {
        "name": "Warner Brothers",
        "entity_type": "business",
        "context_keywords": ["Property of", "Shooting Draft"],
        "expected_risk_category": "business_location"
    },
    {
        "name": "THE BULLETIN",
        "entity_type": "business",
        "context_keywords": ["plaque", "bulletin office"],
        "expected_risk_category": "business_location"
    },
    {
        "name": "A free press for a free people.",
        "entity_type": "quote_or_literary_reference",
        "context_keywords": ["free press", "plaque"],
        "expected_risk_category": "literary_rights"
    },
    {
        "name": "THE NEW BULLETIN",
        "entity_type": "business",
        "context_keywords": ["streamlined newspaper"],
        "expected_risk_category": "business_location"
    },
    {
        "name": "HENRY CONNELL",
        "entity_type": "character_name",
        "context_keywords": ["sign-painter", "HenryConnell's name"],
        "expected_risk_category": "name_collision"
    },
    {
        "name": "ANN MITCHELL",
        "entity_type": "character_name",
        "context_keywords": ["girl", "lead female"],
        "expected_risk_category": "name_collision"
    },
    {
        "name": "POP DWYER",
        "entity_type": "character_name",
        "context_keywords": ["veteran newspaperman"],
        "expected_risk_category": "name_collision"
    }
]

APP_NAME = "extraction_validation"
USER_ID = "validator"
SESSION_ID = "validation_session"

async def extract_and_validate():
    """Extract entities and validate against expected results."""
    
    pdf_path = os.path.join(project_root, "tests", "scripts", "Screenplay_1.pdf")
    doc = fitz.open(pdf_path)
    
    # Extract first 2 pages
    full_text = ""
    num_pages = min(2, len(doc))
    for page_num in range(num_pages):
        full_text += f"\n\n--- Page {page_num + 1} ---\n{doc[page_num].get_text()}"
    doc.close()
    
    # Set up extraction
    session_service = InMemorySessionService()
    runner = Runner(agent=extraction_agent.extractor, app_name=APP_NAME, session_service=session_service)
    
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    
    user_content = types.Content(role="user", parts=[types.Part(text=full_text)])
    
    final_response_text = None
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=user_content):
        if event.is_final_response() and event.content and event.content.parts:
            final_response_text = event.content.parts[0].text
    
    # Parse and validate
    parsed = json.loads(final_response_text)
    entities = Entities.model_validate(parsed)
    
    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print(f"\nExtracted {len(entities.entities)} entities from {num_pages} pages")
    print(f"Expected at least {len(EXPECTED_ENTITIES)} entities\n")
    
    # Validation checks
    found_count = 0
    found_exact = 0
    validation_errors = []
    
    for expected in EXPECTED_ENTITIES:
        found_exact_match = None
        found_partial = None
        
        for actual in entities.entities:
            # Exact name match
            if actual.name == expected["name"]:
                found_exact_match = actual
                found_exact += 1
                break
            
            # Check if name appears in actual (case-insensitive)
            if expected["name"].lower() in actual.name.lower():
                found_partial = actual
        
        if found_exact_match:
            found_count += 1
            # Verify risk category
            if found_exact_match.risk_category.value != expected["expected_risk_category"]:
                validation_errors.append(
                    f"  ❌ {expected['name']}: Expected risk '{expected['expected_risk_category']}', "
                    f"got '{found_exact_match.risk_category.value}'"
                )
            else:
                print(f"  ✓ {expected['name']}: Correct type and risk category")
        elif found_partial:
            found_count += 1
            print(f"  ⚠ {expected['name']}: Partial match '{found_partial.name}'")
        else:
            validation_errors.append(f"  ❌ {expected['name']}: NOT FOUND")
    
    print("\n" + "-" * 60)
    print(f"Expected: {len(EXPECTED_ENTITIES)} | Found: {found_count} | Exact: {found_exact}")
    print("-" * 60)
    
    if validation_errors:
        print("\nVALIDATION ERRORS:")
        for err in validation_errors:
            print(err)
        return False
    else:
        print("\n✓ ALL EXPECTED ENTITIES DETECTED CORRECTLY")
        return True

if __name__ == "__main__":
    result = asyncio.run(extract_and_validate())
    sys.exit(0 if result else 1)