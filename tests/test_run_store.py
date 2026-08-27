"""
tests/test_run_store.py

End-to-end test for the storage layer against REAL Firestore.

Tests:
1. Create a run, verify it exists
2. Save pipeline results with all entity fields (including depiction_context, ambiguity_reason)
3. Read it back and verify all fields survived
4. Record decisions and verify summary counts are recomputed
5. Attach a report and verify report_file_url + report_hash
6. Clean up - delete the test document
"""

import os
import sys
import uuid
import json
from datetime import datetime, timezone

# Set up environment from .env file BEFORE importing anything else
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

# Add project root to path
sys.path.insert(0, project_root)

from schemas.entities import Entity, Entities, EntityType, ScriptLocation
from schemas.risk_result import RiskLevel
from storage.file_store import upload_report
from storage.firestore_run_store import (
    create_run,
    save_pipeline_results,
    record_decision,
    attach_report,
    get_run,
    recompute_summary,
    _compute_summary_from_entities,
)


def test_storage_round_trip():
    """Test the complete storage round-trip against REAL Firestore."""
    
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"
    script_id = "test_script_001"
    script_title = "Test Screenplay"
    script_file_url = f"gs://script-clearance-scripts/runs/{run_id}/test_screenplay.txt"
    report_url = f"gs://script-clearance-scripts/runs/{run_id}/clearance_report.pdf"
    
    print("\n" + "="*70)
    print(f"Testing Storage Layer - Run ID: {run_id}")
    print("="*70)
    
    # Test 1: Create a run
    print("\nTEST 1: Create a run")
    print("-" * 40)
    
    run_doc = create_run(run_id, script_id, script_title, script_file_url)
    
    assert run_doc["run_id"] == run_id
    assert run_doc["script_id"] == script_id
    assert run_doc["script_title"] == script_title
    assert run_doc["script_file_url"] == script_file_url
    assert run_doc["status"] == "processing"
    assert "created_at" in run_doc
    assert "audit_log" in run_doc
    assert isinstance(run_doc["audit_log"], list), f"audit_log should be a list, got {type(run_doc['audit_log'])}"
    assert len(run_doc["audit_log"]) == 1
    assert run_doc["audit_log"][0]["event_type"] == "run_created"
    
    print("✓ Run created successfully")
    print(f"  Status: {run_doc['status']}")
    print(f"  Audit log: {len(run_doc['audit_log'])} entries")
    print()
    
    # Test 2: Save pipeline results
    print("TEST 2: Save pipeline results")
    print("-" * 40)
    
    entities_data = {
        "run_id": run_id,
        "script_id": script_id,
        "script_title": script_title,
        "entities": [
            Entity(
                name="MCDONALD'S",
                entity_type=EntityType.BUSINESS,
                context="Scene context for McDonald's.",
                location=ScriptLocation(page_number=1, scene_number=1, line_excerpt="Line with MCDONALD'S"),
                confidence=0.95,
                requires_human_review=False,
                depiction_context="neutral",
                ambiguity_reason=None,
                extraction_notes="Clear brand reference",
            ),
            Entity(
                name="HENRY CONNELL",
                entity_type=EntityType.CHARACTER_NAME,
                context="Scene context for character.",
                location=ScriptLocation(page_number=1, scene_number=1, line_excerpt="HENRY CONNELL speaks"),
                confidence=0.98,
                requires_human_review=False,
                depiction_context="neutral",
                ambiguity_reason=None,
                extraction_notes="Protagonist name",
            ),
            Entity(
                name="TIME",
                entity_type=EntityType.LOGO_BRAND,
                context="Scene context for TIME.",
                location=ScriptLocation(page_number=1, scene_number=1, line_excerpt="TIME magazine visible"),
                confidence=0.92,
                requires_human_review=False,
                depiction_context="on-screen",
                ambiguity_reason=None,
                extraction_notes="Visible brand on screen",
            ),
        ],
        "metadata": {
            "model_used": "gemini-3.6-flash",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "extraction_agent_version": "0.1.0",
            "total_pages_scanned": 1,
        },
    }
    
    entities = Entities.model_validate(entities_data)
    
    run_doc = save_pipeline_results(
        run_id=run_id,
        entities=entities,
        summary_text="Test clearance run completed successfully with 3 entities found.",
        metadata=entities.metadata.model_dump(mode="json"),
        processing_time_seconds=45.5,
    )
    
    assert run_doc["status"] == "ready_for_review"
    assert len(run_doc["entities"]) == 3
    
    # Verify entities have all fields including depiction_context and ambiguity_reason
    for entity in run_doc["entities"]:
        assert "depiction_context" in entity, f"Missing depiction_context in {entity['name']}"
        assert "ambiguity_reason" in entity, f"Missing ambiguity_reason in {entity['name']}"
        assert "risk_level" in entity, f"Missing risk_level in {entity['name']}"
        assert "decision_status" in entity, f"Missing decision_status in {entity['name']}"
        print(f"  Entity: {entity['name']}")
        print(f"    depiction_context: {entity.get('depiction_context')}")
        print(f"    ambiguity_reason: {entity.get('ambiguity_reason')}")
    
    # Verify summary counts
    summary = run_doc["summary"]
    assert summary["total_entities"] == 3
    assert summary["counts_by_risk"]["caution"] == 3
    assert summary["counts_by_status"]["pending"] == 3
    assert summary["processing_time_seconds"] == 45.5
    
    print("✓ Pipeline results saved with all entity fields")
    print(f"  Summary counts: {json.dumps(summary, indent=4)}")
    print()
    
    # Test 3: Record decisions
    print("TEST 3: Record decisions")
    print("-" * 40)
    
    entity_to_approve = run_doc["entities"][1]["entity_id"]
    entity_to_block = run_doc["entities"][2]["entity_id"]
    
    run_doc = record_decision(
        run_id=run_id,
        entity_id=entity_to_approve,
        decision_status="approved",
        reason="False positive - fictional character",
        decided_by="test_reviewer",
    )
    
    print(f"✓ Entity {entity_to_approve[:8]}... approved")
    
    run_doc = record_decision(
        run_id=run_id,
        entity_id=entity_to_block,
        decision_status="blocked",
        reason="Trademark usage requires clearance",
        decided_by="test_reviewer",
    )
    
    print(f"✓ Entity {entity_to_block[:8]}... blocked")
    
    # Verify audit_log has decision entries (will be a real list from Firestore)
    audit_log = run_doc["audit_log"]
    assert isinstance(audit_log, list), f"audit_log should be a list, got {type(audit_log)}"
    
    decision_entries = [e for e in audit_log if e.get("event_type") == "entity_decision"]
    assert len(decision_entries) == 2, f"Expected 2 decision entries, got {len(decision_entries)}"
    
    # Verify summary counts were recomputed
    summary = run_doc["summary"]
    assert summary["counts_by_status"]["approved"] == 1
    assert summary["counts_by_status"]["blocked"] == 1
    assert summary["counts_by_status"]["pending"] == 1
    
    print("✓ Summary counts recomputed after decisions")
    print(f"  Audit log entries: {len(audit_log)}")
    print()
    
    # Test 4: Attach report
    print("TEST 4: Attach report")
    print("-" * 40)
    
    pdf_content = b"dummy pdf content"
    import hashlib
    expected_hash = hashlib.sha256(pdf_content).hexdigest()
    
    # Upload report to Cloud Storage
    report_url, report_hash = upload_report(run_id, pdf_content)
    print(f"Uploaded report to: {report_url}")
    print(f"Report hash: {report_hash}")
    
    run_doc = attach_report(
        run_id=run_id,
        report_url=report_url,
        report_hash=report_hash,
        exported_by="test_exporter",
    )
    
    assert run_doc["report_file_url"] == report_url
    assert run_doc["report_hash"] == expected_hash
    assert run_doc["exported_by"] == "test_exporter"
    assert "exported_at" in run_doc
    assert run_doc["status"] == "cleared"
    
    # Verify audit_log has exported entry (real list from Firestore)
    audit_log = run_doc["audit_log"]
    assert isinstance(audit_log, list), f"audit_log should be a list, got {type(audit_log)}"
    
    exported_entries = [e for e in audit_log if e.get("event_type") == "exported"]
    assert len(exported_entries) == 1
    
    print("✓ Report attached successfully")
    print(f"  Status: {run_doc['status']}")
    print(f"  Exported by: {run_doc['exported_by']}")
    print()
    
    # Test 5: Get run and verify full document
    print("TEST 5: Get run and verify full document")
    print("-" * 40)
    
    run_doc = get_run(run_id)
    
    assert run_doc is not None
    assert run_doc["run_id"] == run_id
    assert run_doc["script_id"] == script_id
    assert run_doc["script_title"] == script_title
    assert run_doc["script_file_url"] == script_file_url
    assert run_doc["report_file_url"] == report_url
    assert run_doc["report_hash"] == expected_hash
    assert run_doc["status"] == "cleared"
    assert len(run_doc["entities"]) == 3
    
    # Verify audit_log is a real list (Firestore resolved ArrayUnion)
    audit_log = run_doc["audit_log"]
    assert isinstance(audit_log, list), f"audit_log should be a list, got {type(audit_log)}"
    assert len(audit_log) >= 4, f"Expected at least 4 audit entries, got {len(audit_log)}"
    
    print("✓ Full document retrieved correctly")
    print(f"  Run ID: {run_doc['run_id']}")
    print(f"  Status: {run_doc['status']}")
    print(f"  Entities: {len(run_doc['entities'])}")
    print(f"  Audit events: {len(run_doc['audit_log'])}")
    print()
    
    # Test 6: Keep document for console viewing
    print("TEST 6: Keep document for console viewing")
    print("-" * 40)
    
    # Print link to see the document in Firestore console
    print(f"Document available at:")
    print(f"https://console.cloud.google.com/firestore/data?project=script-clearance-hackathon&database=script-clearance-db&collection=clearance_runs&document={run_id}")
    print()
    
    print("Note: Document is NOT deleted so you can view it in Firestore console.")
    print("To clean up manually, delete the document at the link above.")
    print()
    
    print("\n" + "="*70)
    print("ALL TESTS PASSED!")
    print("="*70)
    print()
    
    return True


if __name__ == "__main__":
    try:
        result = test_storage_round_trip()
        if result:
            print("Storage layer test completed successfully.")
            sys.exit(0)
        else:
            print("Storage layer test failed.")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
