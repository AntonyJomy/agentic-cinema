"""
tests/test_api_decisions.py

Server-side review decision endpoints and persistence.
Does not call Gemini or Parallel.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["CLEARANCE_STORE"] = "memory"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ.setdefault("ENVIRONMENT", "development")

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient

from api.main import app
from api.run_store import StoredClearanceRun, get_run_store, reset_run_store_for_tests
from api.schemas import ClearanceEntityResponse, ClearanceResponse, ClearanceRunResponse
from gatekeeper.clearance_gate import evaluate_clearance
from schemas.entities import EntityType
from schemas.legal_review import EntityReviewRecord, LegalReviewPackage, ReviewDecision
from schemas.research_result import Citation
from schemas.risk_result import RiskLevel


def _seed_run(*, high_risk: bool = True, run_id: str = "run-test-1") -> StoredClearanceRun:
    reset_run_store_for_tests()
    entity_id = "entity-1"
    record = EntityReviewRecord(
        entity_id=entity_id,
        entity_name="Acme Corp",
        entity_type=EntityType.BUSINESS,
        context="A storefront appears in scene 1.",
        ai_risk_level=RiskLevel.HIGH_RISK if high_risk else RiskLevel.CLEAR,
        ai_triggered_rule="high_risk_rule",
        ai_reasoning="Placeholder reasoning for persistence tests.",
        ai_research_confidence=0.8,
        ai_finding="A real business match exists.",
        evidence=[
            Citation(
                source_url="https://example.com/acme",
                summary="Business listing",
            )
        ],
        requires_human_review=high_risk,
        decision=ReviewDecision.NEEDS_REVIEW,
    )
    package = LegalReviewPackage(
        run_id=run_id,
        script_id="script-1",
        script_title="Test Script",
        entity_reviews=[record],
        overall_decision=ReviewDecision.NEEDS_REVIEW,
    )
    gatekeeper = evaluate_clearance(package)
    entity = ClearanceEntityResponse(
        entity_id=entity_id,
        name="Acme Corp",
        entity_type="business",
        risk_category="business_location",
        context="A storefront appears in scene 1.",
        location={"page_number": 1, "scene_number": 1, "line_excerpt": "INT. ACME"},
        confidence=0.9,
        requires_human_review=high_risk,
        evidence=[
            {
                "source_url": "https://example.com/acme",
                "summary": "Business listing",
                "retrieved_via": "parallel",
            }
        ],
        status="flagged",
        risk_level="high_risk" if high_risk else "clear",
        research_finding="A real business match exists.",
        legal_decision="needs_review",
    )
    public = ClearanceResponse(
        run=ClearanceRunResponse(
            run_id=run_id,
            script_id="script-1",
            script_title="Test Script",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
            overall_status="flagged" if high_risk else "pending",
            reviewed_by=None,
            reviewed_at=None,
            entities=[entity],
            metadata={"cleared_for_export": gatekeeper.cleared_for_export},
        ),
        summary={"overall_summary": "Test summary", "total_entities": 1},
        legal_review={
            "overall_decision": "needs_review",
            "pending_review_count": 1,
            "unresolved_required_count": 1 if high_risk else 0,
        },
        gatekeeper={
            "status": gatekeeper.status.value,
            "reason": gatekeeper.reason.value,
            "message": gatekeeper.message,
            "cleared_for_export": gatekeeper.cleared_for_export,
        },
        cleared_for_export=gatekeeper.cleared_for_export,
    )
    stored = StoredClearanceRun(
        owner_uid="dev-user",
        public=public,
        legal_review=package,
    )
    get_run_store().save(stored)
    return stored


client = TestClient(app)


def test_get_run_returns_persisted_package():
    _seed_run()
    response = client.get("/clearance/run-test-1")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["run"]["run_id"] == "run-test-1"
    assert payload["run"]["entities"][0]["name"] == "Acme Corp"
    assert payload["cleared_for_export"] is False
    assert payload["run"]["entities"][0].get("ai_reasoning") in (None, "")


def test_entity_decision_is_persisted_and_reloaded():
    _seed_run()
    response = client.post(
        "/clearance/run-test-1/entities/entity-1/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    entity = payload["run"]["entities"][0]
    assert entity["status"] == "cleared"
    assert entity["legal_decision"] == "approved"
    assert payload["run"]["reviewed_by"] == "Development User"

    reloaded = client.get("/clearance/run-test-1")
    assert reloaded.status_code == 200
    assert reloaded.json()["run"]["entities"][0]["status"] == "cleared"


def test_dismiss_maps_to_approved_with_overridden_status():
    _seed_run()
    response = client.post(
        "/clearance/run-test-1/entities/entity-1/decision",
        json={"decision": "approved", "comment": "dismissed"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["run"]["entities"][0]["status"] == "overridden"


def test_block_entity_status():
    _seed_run()
    response = client.post(
        "/clearance/run-test-1/entities/entity-1/decision",
        json={"decision": "blocked"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["run"]["entities"][0]["status"] == "blocked"


def test_overall_approval_rejected_while_high_risk_unresolved():
    _seed_run(high_risk=True)
    response = client.post(
        "/clearance/run-test-1/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 409
    payload = client.get("/clearance/run-test-1").json()
    assert payload["run"]["overall_status"] != "approved"
    assert payload["cleared_for_export"] is False


def test_entity_approval_alone_sets_export_and_overall_status():
    """Gatekeeper + overall_status follow entity decisions; no run stamp needed."""
    _seed_run(high_risk=True)
    entity_resp = client.post(
        "/clearance/run-test-1/entities/entity-1/decision",
        json={"decision": "approved"},
    )
    assert entity_resp.status_code == 200, entity_resp.text
    payload = entity_resp.json()
    assert payload["run"]["overall_status"] == "approved"
    assert payload["cleared_for_export"] is True
    assert payload["run"]["reviewed_by"] == "Development User"

    reloaded = client.get("/clearance/run-test-1").json()
    assert reloaded["cleared_for_export"] is True
    assert reloaded["run"]["overall_status"] == "approved"


def test_entity_block_sets_rejected_overall_status():
    _seed_run(high_risk=True)
    response = client.post(
        "/clearance/run-test-1/entities/entity-1/decision",
        json={"decision": "blocked"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["run"]["overall_status"] == "rejected"
    assert payload["cleared_for_export"] is False


def test_frontend_cannot_set_reviewer_identity():
    _seed_run()
    response = client.post(
        "/clearance/run-test-1/entities/entity-1/decision",
        json={
            "decision": "approved",
            "reviewer_name": "Attacker",
            "user_id": "attacker",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["run"]["reviewed_by"] == "Development User"


def test_missing_run_is_404():
    reset_run_store_for_tests()
    response = client.get("/clearance/does-not-exist")
    assert response.status_code == 404


def test_unknown_entity_decision_is_400():
    _seed_run()
    response = client.post(
        "/clearance/run-test-1/entities/missing/decision",
        json={"decision": "approved"},
    )
    assert response.status_code == 400


def test_clearance_rejects_oversized_script(monkeypatch):
    monkeypatch.setenv("MAX_SCRIPT_CHARS", "8")
    response = client.post("/clearance", json={"script": "INT. CAFE - DAY " * 20})
    assert response.status_code == 400
    assert "maximum" in response.json()["detail"].lower()


def test_extract_script_rejects_empty_file():
    response = client.post(
        "/extract-script",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400


def test_extract_script_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr("api.main.max_upload_bytes", lambda: 16)
    response = client.post(
        "/extract-script",
        files={"file": ("big.txt", b"x" * 64, "text/plain")},
    )
    assert response.status_code == 413


def test_citation_rejects_javascript_url():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Citation(
            source_url="javascript:alert(1)",
            summary="malicious",
        )


def test_health_and_docs_enabled_in_development():
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
