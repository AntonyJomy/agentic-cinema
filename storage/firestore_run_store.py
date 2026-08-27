"""
storage/firestore_run_store.py

Firestore persistence for clearance runs.

The document structure is designed for fast dashboard queries:
- Top-level run fields (run_id, status, timestamps, pointers to files)
- Summary block (pre-computed counts for dashboard)
- Full entities array (all findings with decisions)
- Audit log (state changes with actor/timestamp)
- Executive summary (plain-language overview)
- Metadata (extraction details)
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from google.cloud import firestore
from google.cloud.firestore_v1.transforms import ArrayUnion

from schemas.entities import Entity, EntityType, RiskCategory
from schemas.risk_result import RiskLevel

if TYPE_CHECKING:
    from schemas.entities import Entities
    from schemas.summary_result import SummaryResult

load_dotenv()


def _convert_firestore_value(val):
    """Convert Firestore ArrayUnion to list for Python compatibility."""
    # Check for ArrayUnion-like objects (has __iter__ and __len__ or is a list)
    if isinstance(val, ArrayUnion):
        try:
            return list(val.elements)
        except AttributeError:
            # Fallback for mock objects
            return list(val) if hasattr(val, '__iter__') else val
    return val


def _convert_firestore_dict(data: dict) -> dict:
    """Convert Firestore document data, handling ArrayUnion objects."""
    return {k: _convert_firestore_value(v) for k, v in data.items()}

FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "script-clearance-hackathon")
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "script-clearance-db")
COLLECTION = "clearance_runs"


def _get_firestore_client() -> firestore.Client:
    """Get a Firestore client with the correct database."""
    return firestore.Client(
        project=FIRESTORE_PROJECT,
        database=FIRESTORE_DATABASE,
    )


def _now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def _compute_summary_from_entities(entities: list[dict]) -> dict:
    """
    Re-compute the summary block from the entities array.
    
    This is called whenever entities change (pipeline results saved, decisions recorded).
    The dashboard reads this pre-computed block instead of aggregating on read.
    """
    counts_by_risk = {"clear": 0, "caution": 0, "high_risk": 0}
    counts_by_status = {"pending": 0, "approved": 0, "blocked": 0, "dismissed": 0}
    counts_by_entity_type = {}
    high_risk_unresolved = 0
    
    for entity in entities:
        # Count by risk level
        risk_level = entity.get("risk_level", "caution")
        if risk_level in counts_by_risk:
            counts_by_risk[risk_level] += 1
        else:
            counts_by_risk["caution"] += 1
        
        # Count by decision status
        status = entity.get("decision_status", "pending")
        if status in counts_by_status:
            counts_by_status[status] += 1
        else:
            counts_by_status["pending"] += 1
        
        # Count by entity type
        entity_type = entity.get("entity_type", "unknown")
        counts_by_entity_type[entity_type] = counts_by_entity_type.get(entity_type, 0) + 1
        
        # Count high-risk unresolved
        if risk_level == "high_risk" and status == "pending":
            high_risk_unresolved += 1
    
    total_entities = len(entities)
    
    return {
        "total_entities": total_entities,
        "counts_by_risk": counts_by_risk,
        "counts_by_status": counts_by_status,
        "counts_by_entity_type": counts_by_entity_type,
        "high_risk_unresolved": high_risk_unresolved,
    }


def create_run(run_id: str, script_id: str, script_title: str | None, script_file_url: str) -> dict:
    """
    Create a new clearance run document in Firestore.
    
    Initial state: status="processing", empty entities/audit_log.
    """
    client = _get_firestore_client()
    doc_ref = client.collection(COLLECTION).document(run_id)
    
    now = _now()
    now_iso = now.isoformat()
    
    document = {
        "run_id": run_id,
        "script_id": script_id,
        "script_title": script_title,
        "script_file_url": script_file_url,
        "report_file_url": None,
        "report_hash": None,
        "status": "processing",
        "created_at": now,
        "updated_at": now,
        "reviewed_by": None,
        "reviewed_at": None,
        "exported_by": None,
        "exported_at": None,
        "summary": {
            "total_entities": 0,
            "counts_by_risk": {"clear": 0, "caution": 0, "high_risk": 0},
            "counts_by_status": {"pending": 0, "approved": 0, "blocked": 0, "dismissed": 0},
            "counts_by_entity_type": {},
            "high_risk_unresolved": 0,
            "processing_time_seconds": 0.0,
        },
        "entities": [],
        "audit_log": firestore.ArrayUnion([
            {
                "event_type": "run_created",
                "actor": "system",
                "detail": "Run created",
                "timestamp": now,
            }
        ]),
        "executive_summary": "",
        "metadata": {},
    }
    
    doc_ref.set(document)
    # Get and convert to ensure ArrayUnion is converted to list
    return _convert_firestore_dict(doc_ref.get().to_dict())


def save_pipeline_results(
    run_id: str,
    entities: Entities,
    summary_text: str,
    metadata: dict,
    processing_time_seconds: float,
) -> dict:
    """
    Save pipeline results to the run document.
    
    - Writes all entities with their risk levels and decisions
    - Updates summary block (recomputed from entities)
    - Sets status to "ready_for_review"
    - Logs "pipeline_completed" event
    """
    client = _get_firestore_client()
    doc_ref = client.collection(COLLECTION).document(run_id)
    
    # Convert entities to Firestore format with risk and decision info
    entity_docs = []
    for entity in entities.entities:
        entity_doc = entity.model_dump(mode="json")
        
        # Add default values for storage-specific fields
        entity_doc.setdefault("risk_level", "caution")
        entity_doc.setdefault("triggered_rule", "not_scanned")
        entity_doc.setdefault("evidence", [])
        entity_doc.setdefault("decision_status", "pending")
        entity_doc.setdefault("decision_reason", None)
        entity_doc.setdefault("decided_by", None)
        entity_doc.setdefault("decided_at", None)
        
        entity_docs.append(entity_doc)
    
    # Compute summary from entities
    summary = _compute_summary_from_entities(entity_docs)
    summary["processing_time_seconds"] = processing_time_seconds
    
    # Build audit log entry
    now = _now()
    audit_entry = {
        "event_type": "pipeline_completed",
        "actor": "system",
        "detail": f"Pipeline completed: {entities.entity_count} entities found",
        "timestamp": now,
    }
    
    # Update document
    update_data = {
        "status": "ready_for_review",
        "updated_at": now,
        "summary": summary,
        "entities": entity_docs,
        "executive_summary": summary_text,
        "metadata": metadata,
        "audit_log": firestore.ArrayUnion([audit_entry]),
    }
    
    doc_ref.update(update_data)
    return _convert_firestore_dict(doc_ref.get().to_dict())


def record_decision(
    run_id: str,
    entity_id: str,
    decision_status: str,
    reason: str | None,
    decided_by: str,
) -> dict:
    """
    Record a decision for a specific entity.
    
    - Updates the entity's decision fields
    - Recomputes summary counts
    - Appends audit log entry
    """
    client = _get_firestore_client()
    doc_ref = client.collection(COLLECTION).document(run_id)
    
    # Get current document
    doc = doc_ref.get()
    if not doc.exists:
        raise ValueError(f"Run {run_id} not found")
    
    data = doc.to_dict() or {}
    entities = data.get("entities", [])
    
    # Find and update the entity
    updated_entities = []
    found = False
    for entity in entities:
        if entity.get("entity_id") == entity_id:
            found = True
            now = _now()
            entity = entity.copy()
            entity["decision_status"] = decision_status
            entity["decision_reason"] = reason
            entity["decided_by"] = decided_by
            entity["decided_at"] = now
        updated_entities.append(entity)
    
    if not found:
        raise ValueError(f"Entity {entity_id} not found in run {run_id}")
    
    # Compute updated summary
    summary = _compute_summary_from_entities(updated_entities)
    
    # Build audit log entry
    now = _now()
    audit_entry = {
        "event_type": "entity_decision",
        "actor": decided_by,
        "detail": f"Entity {entity_id}: {decision_status}",
        "timestamp": now,
    }
    
    # Update document
    update_data = {
        "status": "ready_for_review",  # Status doesn't change until run-level decision
        "updated_at": now,
        "summary": summary,
        "entities": updated_entities,
        "audit_log": firestore.ArrayUnion([audit_entry]),
    }
    
    doc_ref.update(update_data)
    return _convert_firestore_dict(doc_ref.get().to_dict())


def attach_report(
    run_id: str,
    report_url: str,
    report_hash: str,
    exported_by: str,
) -> dict:
    """
    Attach the generated PDF report to the run.
    
    - Sets report_file_url and report_hash
    - Updates status to "cleared" or "blocked" based on gatekeeper
    - Sets exported_by and exported_at
    - Appends "exported" audit entry
    """
    client = _get_firestore_client()
    doc_ref = client.collection(COLLECTION).document(run_id)
    
    # Get current document to determine final status
    doc = doc_ref.get()
    if not doc.exists:
        raise ValueError(f"Run {run_id} not found")
    
    data = doc.to_dict() or {}
    
    # Determine final status
    current_status = data.get("status", "pending")
    if current_status in ("ready_for_review", "processing"):
        final_status = "cleared"
    else:
        final_status = current_status
    
    now = _now()
    audit_entry = {
        "event_type": "exported",
        "actor": exported_by,
        "detail": f"Report generated and exported",
        "timestamp": now,
    }
    
    update_data = {
        "report_file_url": report_url,
        "report_hash": report_hash,
        "status": final_status,
        "updated_at": now,
        "exported_by": exported_by,
        "exported_at": now,
        "audit_log": firestore.ArrayUnion([audit_entry]),
    }
    
    doc_ref.update(update_data)
    return _convert_firestore_dict(doc_ref.get().to_dict())


def get_run(run_id: str) -> dict | None:
    """Get a run document by ID."""
    client = _get_firestore_client()
    doc = client.collection(COLLECTION).document(run_id).get()
    if not doc.exists:
        return None
    return _convert_firestore_dict(doc.to_dict())


def recompute_summary(run_id: str) -> dict:
    """
    Recompute the summary block from the entities array.
    
    Use this if entities are modified outside the normal flow.
    """
    client = _get_firestore_client()
    doc_ref = client.collection(COLLECTION).document(run_id)
    
    doc = doc_ref.get()
    if not doc.exists:
        raise ValueError(f"Run {run_id} not found")
    
    data = doc.to_dict() or {}
    entities = data.get("entities", [])
    
    summary = _compute_summary_from_entities(entities)
    
    doc_ref.update({
        "summary": summary,
        "updated_at": _now(),
    })
    
    return _convert_firestore_dict(doc_ref.get().to_dict())
