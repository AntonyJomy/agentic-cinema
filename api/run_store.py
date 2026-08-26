"""
api/run_store.py

Persistence for authoritative clearance runs.

The browser is never the database. Runs are stored under clearance_runs
and reloaded for review, overall decision, and the final report.

Backends:
  - firestore: Google Cloud Firestore (project/database from settings)
  - memory: process-local dict (tests and local MVP without GCP credentials)
  - auto: try Firestore, fall back to memory

TODO(firebase-auth): After Firebase Authentication exists, keep owner_uid
checks and optionally scope queries by the verified uid.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Protocol

from pydantic import BaseModel, Field

from api.settings import (
    clearance_store_backend,
    firestore_database,
    firestore_project,
)
from schemas.legal_review import LegalReviewPackage, ReviewDecision
from schemas.gatekeeper_result import GatekeeperResult, GatekeeperStatus
from gatekeeper.clearance_gate import evaluate_clearance
from legal_review.review_workflow import record_entity_decision, record_overall_decision

from api.schemas import ClearanceEntityResponse, ClearanceResponse, ClearanceRunResponse
from api.url_safety import sanitize_evidence_items

logger = logging.getLogger("agentic_cinema.store")

COLLECTION = "clearance_runs"


class StoredClearanceRun(BaseModel):
    """Server-side clearance record: public API view + full review package."""

    owner_uid: str
    reviewer_uid: str | None = None
    public: ClearanceResponse
    legal_review: LegalReviewPackage
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def compute_overall_status(
    package: LegalReviewPackage,
    gatekeeper: GatekeeperResult,
) -> str:
    """Derive run-level UI status from entity reviews + gatekeeper.

    No separate run-level Approve/Block stamp is required: export eligibility
    and overall status follow the gatekeeper once entity decisions are recorded.
    """
    if package.overall_decision == ReviewDecision.BLOCKED:
        return "rejected"
    if any(r.decision == ReviewDecision.BLOCKED for r in package.entity_reviews):
        return "rejected"
    if gatekeeper.cleared_for_export:
        return "approved"
    if gatekeeper.status == GatekeeperStatus.BLOCKED:
        return "flagged"
    return "pending"


def _entity_status(record) -> str:
    if record is None:
        return "flagged"
    if record.decision == ReviewDecision.APPROVED:
        comment = (record.comment or "").strip().lower()
        if comment.startswith("dismiss"):
            return "overridden"
        return "cleared"
    if record.decision == ReviewDecision.BLOCKED:
        return "blocked"
    return "flagged"


def _public_legal_review(package: LegalReviewPackage) -> dict:
    return {
        "overall_decision": package.overall_decision.value,
        "reviewed_by": package.reviewed_by,
        "reviewed_at": (
            package.reviewed_at.isoformat() if package.reviewed_at else None
        ),
        "pending_review_count": package.pending_review_count,
        "unresolved_required_count": package.unresolved_required_count,
    }


def _public_gatekeeper(gatekeeper: GatekeeperResult) -> dict:
    return {
        "status": gatekeeper.status.value,
        "reason": gatekeeper.reason.value,
        "message": gatekeeper.message,
        "cleared_for_export": gatekeeper.cleared_for_export,
    }


def _public_summary(summary: dict | None) -> dict | None:
    if not summary:
        return None
    return {
        "overall_summary": summary.get("overall_summary"),
        "clear_count": summary.get("clear_count"),
        "caution_count": summary.get("caution_count"),
        "high_risk_count": summary.get("high_risk_count"),
        "total_entities": summary.get("total_entities"),
        "priority_items": summary.get("priority_items") or [],
    }


def _public_metadata(metadata: dict | None) -> dict:
    meta = dict(metadata or {})
    for key in (
        "model_used",
        "extraction_agent_version",
        "extracted_at",
    ):
        meta.pop(key, None)
    return meta


def sanitize_public_response(response: ClearanceResponse) -> ClearanceResponse:
    """Strip internal pipeline fields from a client-facing payload."""
    run = response.run
    entities: list[ClearanceEntityResponse] = []
    for entity in run.entities:
        data = entity.model_dump(mode="json")
        data["evidence"] = sanitize_evidence_items(data.get("evidence"))
        data["ai_reasoning"] = None
        data["triggered_rule"] = None
        data["extraction_notes"] = None
        entities.append(ClearanceEntityResponse.model_validate(data))

    public_run = run.model_copy(
        update={
            "entities": entities,
            "metadata": _public_metadata(run.metadata),
        }
    )
    return response.model_copy(
        update={
            "run": public_run,
            "summary": _public_summary(response.summary),
            "legal_review": response.legal_review,
            "gatekeeper": response.gatekeeper,
        }
    )


def refresh_public_from_package(
    stored: StoredClearanceRun,
    package: LegalReviewPackage,
    gatekeeper: GatekeeperResult,
    *,
    reviewer_display_name: str | None = None,
) -> StoredClearanceRun:
    """Rebuild the public API document after a server-side decision."""
    review_by_id = {record.entity_id: record for record in package.entity_reviews}
    updated_entities: list[ClearanceEntityResponse] = []
    for entity in stored.public.run.entities:
        record = review_by_id.get(entity.entity_id)
        updated_entities.append(
            entity.model_copy(
                update={
                    "status": _entity_status(record),
                    "legal_decision": record.decision.value if record else entity.legal_decision,
                    "ai_reasoning": None,
                    "triggered_rule": None,
                    "extraction_notes": None,
                    "evidence": sanitize_evidence_items(
                        [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in (entity.evidence or [])]
                        if entity.evidence
                        else []
                    ),
                }
            )
        )

    now = datetime.now(timezone.utc).isoformat()
    display_reviewer = reviewer_display_name or package.reviewed_by
    run = stored.public.run.model_copy(
        update={
            "entities": updated_entities,
            "overall_status": compute_overall_status(package, gatekeeper),
            "reviewed_by": display_reviewer,
            "reviewed_at": (
                package.reviewed_at.isoformat() if package.reviewed_at else stored.public.run.reviewed_at
            ),
            "updated_at": now,
            "metadata": {
                **_public_metadata(stored.public.run.metadata),
                "cleared_for_export": gatekeeper.cleared_for_export,
                "gatekeeper_status": gatekeeper.status.value,
                "gatekeeper_reason": gatekeeper.reason.value,
            },
        }
    )
    public = stored.public.model_copy(
        update={
            "run": run,
            "legal_review": _public_legal_review(package),
            "gatekeeper": _public_gatekeeper(gatekeeper),
            "cleared_for_export": gatekeeper.cleared_for_export,
            "summary": _public_summary(stored.public.summary),
        }
    )
    return stored.model_copy(
        update={
            "public": public,
            "legal_review": package,
            "updated_at": now,
        }
    )


class RunStore(Protocol):
    def save(self, stored: StoredClearanceRun) -> None: ...

    def get(self, run_id: str) -> StoredClearanceRun | None: ...

    def clear(self) -> None: ...


class MemoryRunStore:
    """Process-local store used for tests and Firestore-unavailable MVP."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, StoredClearanceRun] = {}

    def save(self, stored: StoredClearanceRun) -> None:
        run_id = stored.public.run.run_id
        with self._lock:
            self._runs[run_id] = stored

    def get(self, run_id: str) -> StoredClearanceRun | None:
        with self._lock:
            stored = self._runs.get(run_id)
        return stored.model_copy(deep=True) if stored else None

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


class FirestoreRunStore:
    """Persists clearance runs in the existing clearance_runs collection."""

    def __init__(self, client) -> None:
        self._client = client
        self._collection = client.collection(COLLECTION)

    def save(self, stored: StoredClearanceRun) -> None:
        run_id = stored.public.run.run_id
        payload = stored.model_dump(mode="json")
        payload["run_id"] = run_id
        payload["script_id"] = stored.public.run.script_id
        payload["script_title"] = stored.public.run.script_title
        payload["overall_status"] = stored.public.run.overall_status
        payload["reviewed_by"] = stored.public.run.reviewed_by
        payload["reviewed_at"] = stored.public.run.reviewed_at
        payload["entities"] = [e.model_dump(mode="json") for e in stored.public.run.entities]
        payload["cleared_for_export"] = stored.public.cleared_for_export
        self._collection.document(run_id).set(payload)

    def get(self, run_id: str) -> StoredClearanceRun | None:
        snap = self._collection.document(run_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return StoredClearanceRun.model_validate(data)

    def clear(self) -> None:
        raise NotImplementedError("Refusing to wipe the Firestore collection")


_store: RunStore | None = None
_store_lock = threading.Lock()


def _try_firestore() -> RunStore | None:
    try:
        from google.cloud import firestore

        client = firestore.Client(
            project=firestore_project(),
            database=firestore_database(),
        )
        # Cheap sanity check: client construction succeeded.
        logger.info(
            "Using Firestore run store (%s / %s)",
            firestore_project(),
            firestore_database(),
        )
        return FirestoreRunStore(client)
    except Exception:
        logger.warning(
            "Firestore unavailable; using in-memory clearance run store. "
            "Set CLEARANCE_STORE=firestore with credentials to persist across restarts.",
            exc_info=True,
        )
        return None


def get_run_store() -> RunStore:
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        backend = clearance_store_backend()
        if backend == "memory":
            _store = MemoryRunStore()
            logger.info("Using in-memory clearance run store (CLEARANCE_STORE=memory)")
        elif backend == "firestore":
            store = _try_firestore()
            if store is None:
                raise RuntimeError("CLEARANCE_STORE=firestore but Firestore is unavailable")
            _store = store
        else:
            _store = _try_firestore() or MemoryRunStore()
        return _store


def reset_run_store_for_tests() -> MemoryRunStore:
    """Replace the process store with a fresh memory store (tests only)."""
    global _store
    with _store_lock:
        _store = MemoryRunStore()
        return _store


def apply_entity_decision(
    stored: StoredClearanceRun,
    *,
    entity_id: str,
    decision: ReviewDecision,
    reviewer_uid: str,
    reviewer_name: str,
    comment: str | None = None,
) -> StoredClearanceRun:
    package = record_entity_decision(
        stored.legal_review,
        entity_id,
        decision,
        reviewer_uid,
        comment=comment,
    )
    gatekeeper = evaluate_clearance(package)
    updated = refresh_public_from_package(
        stored,
        package,
        gatekeeper,
        reviewer_display_name=reviewer_name,
    )
    updated.reviewer_uid = reviewer_uid
    return updated


def apply_overall_decision(
    stored: StoredClearanceRun,
    *,
    decision: ReviewDecision,
    reviewer_uid: str,
    reviewer_name: str,
    comment: str | None = None,
) -> StoredClearanceRun:
    package = record_overall_decision(
        stored.legal_review,
        decision,
        reviewer_uid,
        comment=comment,
    )
    gatekeeper = evaluate_clearance(package)
    updated = refresh_public_from_package(
        stored,
        package,
        gatekeeper,
        reviewer_display_name=reviewer_name,
    )
    updated.reviewer_uid = reviewer_uid
    # Overall decision display name belongs on the run, not only entity records.
    run = updated.public.run.model_copy(
        update={
            "reviewed_by": reviewer_name,
            "reviewed_at": package.reviewed_at.isoformat() if package.reviewed_at else None,
            "overall_status": compute_overall_status(package, gatekeeper),
        }
    )
    public = updated.public.model_copy(update={"run": run})
    return updated.model_copy(update={"public": public})
