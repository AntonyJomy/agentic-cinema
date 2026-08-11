"""
tests/test_extraction_agent.py

Tests the extraction agent by running it against a sample screenplay
and verifying the output validates against the Entities schema.
"""
import os
import sys

# Set up environment from .env file BEFORE importing anything else
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

# Add project root to path
sys.path.insert(0, project_root)

from agents.extraction_agent import extractor
from schemas.entities import Entities
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import asyncio
import json

APP_NAME = "extraction_test"
USER_ID = "test_user"
SESSION_ID = "test_session"

async def test_extraction_agent():
    """Run the extraction agent against a test screenplay and validate output."""
    
    # Load the test screenplay
    screenplay_path = os.path.join(project_root, "tests", "scripts", "test_screenplay.txt")
    with open(screenplay_path, "r", encoding="utf-8") as f:
        screenplay_text = f.read()
    
    print(f"Loaded screenplay from: {screenplay_path}")
    print(f"Screenplay length: {len(screenplay_text)} characters\n")
    
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
    print("Running extraction agent...")
    user_content = types.Content(role="user", parts=[types.Part(text=screenplay_text)])
    
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
    
    # Inject real metadata - Gemini may invent fake timestamps, so we override
    from datetime import datetime, timezone
    
    parsed_data["metadata"] = {
        "model_used": "gemini-3.6-flash",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "extraction_agent_version": "0.1.0",
        "total_pages_scanned": parsed_data.get("metadata", {}).get("total_pages_scanned")
    }
    
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
    
    # Check that risk_category auto-populated correctly (proving validators work)
    for entity in entities.entities:
        if entity.risk_category is None:
            print(f"\n--- FAILED: Entity '{entity.name}' has no risk_category ---\n")
            return False
        print(f"Entity: '{entity.name}' | Type: {entity.entity_type} | Risk Category: {entity.risk_category}")
    
    print("\n--- PASSED: All entities have auto-derived risk_category ---\n")
    
    # Print full JSON output
    print("\n--- Full Entities JSON Output ---\n")
    print(entities.model_dump_json(indent=2))
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Extraction Agent")
    print("=" * 60 + "\n")
    
    result = asyncio.run(test_extraction_agent())
    
    print("\n" + "=" * 60)
    if result:
        print("ALL TESTS PASSED")
    else:
        print("TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if result else 1)
