"""
api/response_builder.py

Maps ClearancePipelineResult to frontend-compatible API responses.
"""
from __future__ import annotations

from orchestrator import ClearancePipelineResult, EntityResult
from schemas.legal_review import EntityReviewRecord, ReviewDecision

from api.schemas import ClearanceEntityResponse, ClearanceResponse, ClearanceRunResponse
from api.url_safety import sanitize_evidence_items
from api.run_store import _public_gatekeeper, _public_legal_review, _public_summary, compute_overall_status


def _entity_status(review_record: EntityReviewRecord | None) -> str:
    if review_record is None:
        return "flagged"
    if review_record.decision == ReviewDecision.APPROVED:
        comment = (review_record.comment or "").strip().lower()
        if comment.startswith("dismiss"):
            return "overridden"
        return "cleared"
    if review_record.decision == ReviewDecision.BLOCKED:
        return "blocked"
    return "flagged"


def _build_entity_response(
    result: EntityResult,
    review_record: EntityReviewRecord | None,
) -> ClearanceEntityResponse:
    entity = result.entity
    research = result.research_result
    risk = result.risk_result

    evidence: list[dict] = []
    if risk and risk.evidence:
        evidence = [item.model_dump(mode="json") for item in risk.evidence]
    elif research and research.citations:
        evidence = [item.model_dump(mode="json") for item in research.citations]

    return ClearanceEntityResponse(
        entity_id=entity.entity_id,
        name=entity.name,
        entity_type=entity.entity_type.value,
        risk_category=entity.risk_category.value if entity.risk_category else "",
        context=entity.context,
        location=entity.location.model_dump(mode="json"),
        confidence=entity.confidence,
        requires_human_review=(
            risk.requires_human_review if risk else entity.requires_human_review
        ),
        extraction_notes=None,
        evidence=sanitize_evidence_items(evidence),
        status=_entity_status(review_record),
        risk_level=risk.risk_level.value if risk else None,
        research_finding=research.finding if research else None,
        research_confidence=research.confidence if research else None,
        ai_reasoning=None,
        triggered_rule=None,
        legal_decision=review_record.decision.value if review_record else None,
    )


def build_clearance_response(
    pipeline_result: ClearancePipelineResult,
    *,
    script_title: str | None = None,
    source_file_name: str | None = None,
) -> ClearanceResponse:
    """Convert a pipeline result into the public API response contract."""
    review_by_id = {
        record.entity_id: record for record in pipeline_result.legal_review.entity_reviews
    }

    entities: list[ClearanceEntityResponse] = []
    for results_list in pipeline_result.entity_results.values():
        for result in results_list:
            review_record = review_by_id.get(result.entity.entity_id)
            entities.append(_build_entity_response(result, review_record))

    grounded = pipeline_result.grounded_entities
    title = (
        script_title
        or grounded.script_title
        or pipeline_result.extracted_entities.script_title
        or "Untitled Screenplay"
    )

    gatekeeper = pipeline_result.gatekeeper_result
    overall_status = compute_overall_status(pipeline_result.legal_review, gatekeeper)

    metadata = {
        "extracted_entity_count": pipeline_result.extracted_entities.entity_count,
        "grounded_entity_count": grounded.entity_count,
        "cleared_for_export": gatekeeper.cleared_for_export,
        "gatekeeper_status": gatekeeper.status.value,
        "gatekeeper_reason": gatekeeper.reason.value,
        "total_pages_scanned": grounded.metadata.total_pages_scanned,
    }
    if source_file_name:
        metadata["source_file_name"] = source_file_name

    run = ClearanceRunResponse(
        run_id=grounded.run_id,
        script_id=grounded.script_id,
        script_title=title,
        created_at=pipeline_result.start_time.isoformat(),
        updated_at=pipeline_result.end_time.isoformat(),
        overall_status=overall_status,
        reviewed_by=pipeline_result.legal_review.reviewed_by,
        reviewed_at=(
            pipeline_result.legal_review.reviewed_at.isoformat()
            if pipeline_result.legal_review.reviewed_at
            else None
        ),
        entities=entities,
        metadata=metadata,
    )

    report = pipeline_result.report
    return ClearanceResponse(
        run=run,
        summary=_public_summary(pipeline_result.summary_result.model_dump(mode="json")),
        legal_review=_public_legal_review(pipeline_result.legal_review),
        gatekeeper=_public_gatekeeper(gatekeeper),
        statistics=report.get("statistics"),
        recommendations=report.get("recommendations", []),
        cleared_for_export=gatekeeper.cleared_for_export,
        duration_seconds=pipeline_result.duration_seconds,
    )
