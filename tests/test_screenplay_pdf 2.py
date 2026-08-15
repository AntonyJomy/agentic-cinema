"""
tests/test_screenplay_pdf.py

Tests the extraction agent against a PDF screenplay.
Extracts text from the PDF and sends it to the extraction agent.
"""
import os
import sys
import json
import asyncio

# Set up environment from .env file BEFORE importing anything else
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

# Add project root to path
sys.path.insert(0, project_root)

import fitz  # PyMuPDF
from agents import extraction_agent

extractor = extraction_agent.extractor
from schemas.entities import Entities
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

APP_NAME = "extraction_test_pdf"
USER_ID = "test_user"
SESSION_ID = "test_session_pdf"

async def test_extraction_from_pdf():
    """Extract text from Screenplay_1.pdf and run extraction agent."""
    
    pdf_path = os.path.join(project_root, "tests", "scripts", "Screenplay_1.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file not found at {pdf_path}")
        return False
    
    print(f"Loading PDF from: {pdf_path}\n")
    
    # Extract text from PDF - process all pages
    doc = fitz.open(pdf_path)
    full_text = ""
    num_pages_to_process = len(doc)
    for page_num in range(num_pages_to_process):
        page = doc[page_num]
        text = page.get_text()
        full_text += f"\n\n--- Page {page_num + 1} ---\n{text}"
    
    print(f"Extracted {len(full_text)} characters from {num_pages_to_process} pages\n")
    doc.close()
    
    print("First 500 chars of extracted text:")
    print(full_text[:500])
    print("...\n")
    
    # Set up the runner
    session_service = InMemorySessionService()
    runner = Runner(agent=extractor, app_name=APP_NAME, session_service=session_service)
    
    # Create a session
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )
    
    # Run the extraction agent
    print("Running extraction agent on PDF content...")
    user_content = types.Content(role="user", parts=[types.Part(text=full_text)])
    
    final_response_text = None
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response_text = event.content.parts[0].text
    
    print("\n--- Extraction Agent Response (raw JSON) ---\n")
    print(final_response_text)
    
    # Parse the JSON response
    if final_response_text:
        try:
            parsed_data = json.loads(final_response_text)
            print("\n--- JSON Parsed Successfully ---\n")
        except json.JSONDecodeError as e:
            print(f"\n--- FAILED: Invalid JSON from agent ---\n")
            print(f"Error: {e}")
            print(f"Raw response: {final_response_text}")
            return False
    else:
        print("\n--- FAILED: No final response from agent ---\n")
        return False
    
    # Validate against the Entities schema
    try:
        entities = Entities.model_validate(parsed_data)
        print("--- PASSED: Output validates against Entities schema ---\n")
    except Exception as e:
        print(f"\n--- FAILED: Schema validation error ---\n")
        print(f"Error: {e}")
        return False
    
    # Check that at least one entity was found
    if len(entities.entities) == 0:
        print("\n--- FAILED: No entities were extracted ---\n")
        return False
    
    print(f"--- PASSED: {len(entities.entities)} entities extracted ---\n")
    
    # Print entities by category
    print("--- Extracted Entities ---\n")
    for entity in entities.entities:
        print(f"  '{entity.name}' | Type: {entity.entity_type.value} | Risk: {entity.risk_category.value} | Confidence: {entity.confidence}")
    
    # Print full JSON output
    print("\n--- Full Entities JSON Output ---\n")
    print(entities.model_dump_json(indent=2))
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Extraction Agent on PDF Screenplay")
    print("=" * 60 + "\n")
    
    result = asyncio.run(test_extraction_from_pdf())
    
    print("\n" + "=" * 60)
    if result:
        print("EXTRACTION COMPLETE")
    else:
        print("TEST FAILED")
    print("=" * 60)
    
    sys.exit(0 if result else 1)