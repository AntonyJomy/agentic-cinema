"""
api/progress.py

Sanitize pipeline progress events before they leave the API.

Public events contain only stage/status/count/label — never findings,
reasoning, prompts, exceptions, or model internals.
"""
from __future__ import annotations

from orchestrator import PipelineProgressEvent

PHASE_TO_STAGE = {
    "extraction": "extraction",
    "grounding": "analysis",
    "specialist": "research",
    "risk_scoring": "risks",
    "summary": "summary",
    "legal_review": "legal_review",
    "gatekeeper": "gatekeeper",
}

STAGE_LABELS = {
    "received": "Upload received",
    "extraction": "Extracting script",
    "analysis": "Running analysis",
    "research": "Running specialist reviews",
    "risks": "Evaluating risks",
    "summary": "Preparing summary",
    "legal_review": "Preparing legal review",
    "gatekeeper": "Running gatekeeper",
    "completed": "Completed",
}


def sanitize_progress_event(event: PipelineProgressEvent) -> dict:
    """Map an internal progress event to a client-safe payload."""
    stage = PHASE_TO_STAGE.get(event.phase, "analysis")
    if event.event == "agent_complete":
        status = "failed" if event.status == "failed" else "completed"
    else:
        status = "running"

    payload: dict = {
        "type": "progress",
        "stage": stage,
        "status": status,
        "label": STAGE_LABELS.get(stage, STAGE_LABELS["analysis"]),
    }
    output = event.output if isinstance(event.output, dict) else {}
    count = (
        output.get("entity_count")
        or output.get("grounded_count")
        or output.get("citation_count")
        or output.get("pending_review_count")
        or output.get("total_entities")
    )
    if isinstance(count, int):
        payload["count"] = count
    return payload


def received_event() -> dict:
    return {
        "type": "progress",
        "stage": "received",
        "status": "completed",
        "label": STAGE_LABELS["received"],
    }
