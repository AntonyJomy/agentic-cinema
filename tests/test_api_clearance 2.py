"""
tests/test_api_clearance.py

Tests the FastAPI clearance endpoint wiring.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
SCREENPLAY_PATH = project_root / "tests" / "scripts" / "integration_screenplay.txt"


def test_health_endpoint() -> bool:
    response = client.get("/health")
    if response.status_code != 200:
        print(f"FAILED: health returned {response.status_code}")
        return False
    if response.json().get("status") != "ok":
        print("FAILED: health status not ok")
        return False
    print("PASSED: GET /health")
    return True


def test_clearance_rejects_empty_script() -> bool:
    response = client.post("/clearance", json={"script": "   "})
    if response.status_code not in {400, 422}:
        print(f"FAILED: expected 400/422 for empty script, got {response.status_code}")
        return False
    print("PASSED: POST /clearance rejects empty script")
    return True


def test_clearance_live_pipeline() -> bool:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("SKIPPED: live clearance test (no API key)")
        return True

    script = SCREENPLAY_PATH.read_text(encoding="utf-8")
    response = client.post(
        "/clearance",
        json={"script": script, "script_title": "API Integration Test"},
        timeout=600,
    )

    if response.status_code != 200:
        print(f"FAILED: clearance returned {response.status_code}: {response.text[:500]}")
        return False

    payload = response.json()
    run = payload.get("run", {})
    entities = run.get("entities", [])

    if not run.get("run_id"):
        print("FAILED: response missing run_id")
        return False
    if not entities:
        print("FAILED: response missing entities")
        return False
    if payload.get("gatekeeper") is None:
        print("FAILED: response missing gatekeeper")
        return False
    if payload.get("summary") is None:
        print("FAILED: response missing summary")
        return False

    print(f"PASSED: POST /clearance returned {len(entities)} entities")
    print(f"  Gatekeeper: {payload['gatekeeper']['status']}")
    print(f"  Cleared for export: {payload['cleared_for_export']}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Clearance API")
    print("=" * 60 + "\n")

    ok = test_health_endpoint()
    ok = test_clearance_rejects_empty_script() and ok
    ok = test_clearance_live_pipeline() and ok

    print("\n" + "=" * 60)
    if ok:
        print("ALL TESTS PASSED")
        sys.exit(0)
    print("TESTS FAILED")
    sys.exit(1)
