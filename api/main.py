"""
api/main.py

FastAPI backend for the Agentic Cinema clearance pipeline.

POST /clearance              — run the pipeline
POST /clearance/stream       — stream sanitized progress as NDJSON
POST /extract-script         — extract text from .txt / .pdf
GET  /clearance/{run_id}     — reload an authoritative persisted run
POST /clearance/{run_id}/entities/{entity_id}/decision
POST /clearance/{run_id}/decision
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env", override=True)
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from api.auth import CurrentUser, get_current_user  # noqa: E402
from api.pdf_text import PdfExtractionError, extract_text_from_pdf  # noqa: E402
from api.progress import received_event, sanitize_progress_event  # noqa: E402
from api.response_builder import build_clearance_response  # noqa: E402
from api.run_store import (  # noqa: E402
    StoredClearanceRun,
    apply_entity_decision,
    apply_overall_decision,
    get_run_store,
)
from api.schemas import (  # noqa: E402
    ClearanceRequest,
    ClearanceResponse,
    ClearanceRunResponse,
    EntityDecisionRequest,
    ExtractScriptResponse,
    OverallDecisionRequest,
)
from api.settings import (  # noqa: E402
    cors_origins,
    is_production,
    max_script_chars,
    max_upload_bytes,
    rate_limit_per_minute,
)
from storage.file_store import upload_screenplay as _storage_upload_screenplay  # noqa: E402
from storage.file_store import upload_report as _storage_upload_report  # noqa: E402
from storage.file_store import download_from_gs_url as _storage_download_from_gs_url  # noqa: E402
from storage.firestore_run_store import attach_report as _firestore_attach_report  # noqa: E402
from orchestrator import run_clearance_pipeline  # noqa: E402
from schemas.legal_review import ReviewDecision  # noqa: E402

logger = logging.getLogger("agentic_cinema.api")

_docs = None if is_production() else "/docs"
_redoc = None if is_production() else "/redoc"
_openapi = None if is_production() else "/openapi.json"

app = FastAPI(
    title="Agentic Cinema Clearance API",
    version="0.1.0",
    description="HTTP API for the screenplay E&O clearance agent pipeline.",
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    # Response headers are hidden from cross-origin JS unless named here. The
    # report download relies on all three: the digest and provenance drive
    # tamper-evident verification, and the disposition supplies the filename.
    expose_headers=["X-Report-SHA256", "X-Report-Source", "Content-Disposition"],
)

GENERIC_PIPELINE_ERROR = "Clearance processing failed."

# TODO(firebase-auth): Replace/augment with authenticated per-user rate limiting
# when Firebase Authentication is implemented. This is a coarse IP/global cap
# for the unauthenticated MVP only — it is not equivalent to per-user limits.
_rate_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit_expensive(request: Request) -> None:
    """Basic IP-based limiter for costly POST routes."""
    limit = rate_limit_per_minute()
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_hits[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait and try again.",
        )
    bucket.append(now)


async def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload in chunks and reject it before it exceeds max_bytes."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="Uploaded file exceeds the maximum allowed size.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_script_text(script: str) -> str:
    text = script.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Script text must not be empty")
    limit = max_script_chars()
    if len(text) > limit:
        raise HTTPException(
            status_code=400,
            detail="Script exceeds the maximum allowed length.",
        )
    return text


def _validate_clearance_request(request: ClearanceRequest) -> str:
    script = _validate_script_text(request.script)
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        logger.error("Missing GOOGLE_API_KEY or GEMINI_API_KEY")
        raise HTTPException(
            status_code=503,
            detail="Clearance service is not configured.",
        )
    return script


def _pipeline_error_detail(exc: Exception) -> tuple[int, str]:
    """Map pipeline exceptions to an HTTP status + user-facing detail."""
    message = str(exc).lower()
    if any(
        token in message
        for token in ("503", "unavailable", "high demand", "resource_exhausted", "429")
    ):
        return (
            503,
            "The clearance service is temporarily unavailable. Please try again.",
        )
    if "404" in message or "not_found" in message or "no longer available" in message:
        return (
            503,
            "The AI model is unavailable for this API key. Check GEMINI_MODEL in .env.",
        )
    if "no entities" in message or "no grounded" in message:
        return (422, "No clearance entities could be extracted from this script.")
    return (500, GENERIC_PIPELINE_ERROR)


def _load_owned_run(run_id: str, current_user: CurrentUser) -> StoredClearanceRun:
    stored = get_run_store().get(run_id)
    if stored is None or stored.owner_uid != current_user.uid:
        raise HTTPException(status_code=404, detail="Clearance run not found.")
    return stored


def _persist_pipeline(
    pipeline_result,
    public: ClearanceResponse,
    current_user: CurrentUser,
) -> ClearanceResponse:
    stored = StoredClearanceRun(
        owner_uid=current_user.uid,
        public=public,
        legal_review=pipeline_result.legal_review,
    )
    get_run_store().save(stored)
    return public


def _maybe_generate_report(updated: StoredClearanceRun, reviewer_name: str) -> StoredClearanceRun:
    """
    If a run just became cleared_for_export, generate the PDF report,
    upload it to Cloud Storage, record the URL+hash in Firestore via
    attach_report(), and stamp the values onto the stored run so the
    API response includes them immediately.

    Non-fatal: any GCS or PDF error is logged and the run is returned unchanged.
    """
    if not updated.public.cleared_for_export:
        return updated

    run_id = updated.public.run.run_id

    # Skip if the report was already generated for this run
    if updated.public.run.report_file_url:
        return updated

    try:
        from api.report_generator import generate_report_pdf
        pdf_bytes = generate_report_pdf(updated.public)
    except Exception:
        logger.exception("PDF generation failed for run %s", run_id)
        return updated

    try:
        report_url, report_hash = _storage_upload_report(run_id, pdf_bytes)
    except Exception:
        logger.exception("PDF upload failed for run %s", run_id)
        return updated

    try:
        _firestore_attach_report(
            run_id=run_id,
            report_url=report_url,
            report_hash=report_hash,
            exported_by=reviewer_name,
        )
    except Exception:
        logger.warning("attach_report Firestore call failed for run %s", run_id, exc_info=True)
        # Continue — the file is already uploaded; URL+hash are stamped below.

    # Stamp URL and hash onto the in-memory run so the response reflects them.
    stamped_run = updated.public.run.model_copy(
        update={"report_file_url": report_url, "report_hash": report_hash}
    )
    stamped_public = updated.public.model_copy(update={"run": stamped_run})
    updated = updated.model_copy(update={"public": stamped_public})

    logger.info("Clearance report generated for run %s: %s", run_id, report_url)
    return updated


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/me")
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Return the authenticated user's profile information."""
    return {
        "uid": current_user.uid,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
    }


@app.post(
    "/extract-script",
    response_model=ExtractScriptResponse,
    dependencies=[Depends(rate_limit_expensive)],
)
async def extract_script(
    file: UploadFile = File(...),
    script_title: str | None = Form(default=None),
    current_user: CurrentUser = Depends(get_current_user),
) -> ExtractScriptResponse:
    """Extract plain text from an uploaded .txt or .pdf screenplay."""
    _ = current_user
    filename = (file.filename or "upload").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a .txt or .pdf screenplay.",
        )

    raw = await read_upload_limited(file, max_upload_bytes())
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    page_count: int | None = None
    if suffix == ".pdf":
        try:
            script, page_count = extract_text_from_pdf(raw)
        except PdfExtractionError:
            logger.exception("PDF extraction failed")
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from this PDF.",
            ) from None
    else:
        try:
            script = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Could not decode .txt file as UTF-8",
            ) from None

    try:
        script = _validate_script_text(script)
    except HTTPException:
        raise

    title = (script_title or "").strip() or None

    # Generate the stable run_id here, at first contact with the file.
    # This same id must be passed to /clearance so the pipeline, the Cloud
    # Storage path, and the Firestore document all share one identity.
    run_id = str(uuid.uuid4())

    script_file_url: str | None = None
    try:
        # storage/file_store.upload_screenplay signature: (run_id, file_bytes, filename)
        script_file_url = _storage_upload_screenplay(run_id, raw, filename)
    except Exception as exc:
        logger.warning("Failed to upload file to Cloud Storage: %s", exc)
        # Non-fatal — continue without GCS if credentials/bucket are unavailable.

    return ExtractScriptResponse(
        run_id=run_id,
        script=script,
        filename=filename,
        page_count=page_count,
        script_title=title,
        script_file_url=script_file_url,
    )


@app.post(
    "/clearance",
    response_model=ClearanceResponse,
    dependencies=[Depends(rate_limit_expensive)],
)
async def run_clearance(
    request: ClearanceRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ClearanceResponse:
    """Run the full clearance pipeline for a screenplay."""
    script = _validate_clearance_request(request)

    try:
        pipeline_result = await run_clearance_pipeline(
            script,
            screenplay_path="<api>",
            user_id=current_user.uid,
            run_id=request.run_id or None,
        )
    except RuntimeError as exc:
        logger.warning("Pipeline stopped: %s", exc)
        _, detail = _pipeline_error_detail(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    except Exception as exc:
        logger.exception("Clearance pipeline failed")
        status, detail = _pipeline_error_detail(exc)
        raise HTTPException(status_code=status, detail=detail) from exc

    if request.script_title:
        pipeline_result.grounded_entities = pipeline_result.grounded_entities.model_copy(
            update={"script_title": request.script_title.strip()}
        )

    public = build_clearance_response(
        pipeline_result,
        script_title=request.script_title,
        source_file_name=request.source_file_name,
    )

    # Attach the Cloud Storage URL from /extract-script so it is stored on
    # the Firestore document and returned in every subsequent GET response.
    if request.script_file_url:
        public = public.model_copy(
            update={
                "run": public.run.model_copy(
                    update={"script_file_url": request.script_file_url}
                )
            }
        )

    return _persist_pipeline(pipeline_result, public, current_user)


@app.post("/clearance/stream", dependencies=[Depends(rate_limit_expensive)])
async def run_clearance_stream(
    request: ClearanceRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Stream sanitized clearance pipeline progress as newline-delimited JSON."""
    script = _validate_clearance_request(request)

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        await queue.put(received_event())

        async def on_progress(progress_event) -> None:
            await queue.put(sanitize_progress_event(progress_event))

        async def run_pipeline() -> None:
            try:
                pipeline_result = await run_clearance_pipeline(
                    script,
                    screenplay_path="<api>",
                    user_id=current_user.uid,
                    on_progress=on_progress,
                    run_id=request.run_id or None,
                )

                if request.script_title:
                    pipeline_result.grounded_entities = (
                        pipeline_result.grounded_entities.model_copy(
                            update={"script_title": request.script_title.strip()}
                        )
                    )

                public = build_clearance_response(
                    pipeline_result,
                    script_title=request.script_title,
                    source_file_name=request.source_file_name,
                )
                if request.script_file_url:
                    public = public.model_copy(
                        update={
                            "run": public.run.model_copy(
                                update={"script_file_url": request.script_file_url}
                            )
                        }
                    )
                public = _persist_pipeline(pipeline_result, public, current_user)
                await queue.put(
                    {
                        "type": "complete",
                        "duration_seconds": pipeline_result.duration_seconds,
                        "result": public.model_dump(mode="json"),
                    }
                )
            except RuntimeError as exc:
                logger.warning("Streaming pipeline stopped: %s", exc)
                _, detail = _pipeline_error_detail(exc)
                await queue.put({"type": "error", "status": 422, "detail": detail})
            except Exception as exc:
                logger.exception("Streaming clearance pipeline failed")
                status, detail = _pipeline_error_detail(exc)
                await queue.put({"type": "error", "status": status, "detail": detail})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_pipeline())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(item, default=str) + "\n"
        finally:
            if not task.done():
                task.cancel()
                with asyncio.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/clearance/{run_id}", response_model=ClearanceResponse)
async def get_clearance_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> ClearanceResponse:
    """Return the authoritative persisted clearance package."""
    stored = _load_owned_run(run_id, current_user)
    return stored.public


@app.get("/clearance")
async def list_user_clearance_runs(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Return all clearance runs owned by the authenticated user, with dashboard stats.
    
    Response shape matches frontend expectations:
    {
      "runs": [{run_id, script_title, created_at, updated_at, overall_status,
                entity_count, high_count, caution_count, clear_count}],
      "stats": {total_scripts, total_flags, awaiting_review, high_risk_unresolved, clearance_rate}
    }
    """
    store = get_run_store()

    logger.info("Dashboard query for uid=%s", current_user.uid)
    
    # Memory store has no collection — only valid for local/tests. In production
    # this would silently show an empty desk even when Firestore has data.
    if not hasattr(store, '_collection'):
        if is_production():
            logger.error(
                "Dashboard store is not Firestore (got %s); refusing empty fallback",
                type(store).__name__,
            )
            raise HTTPException(
                status_code=503,
                detail="Clearance store unavailable. Check Firestore configuration.",
            )
        return {"runs": [], "stats": {
            "total_scripts": 0,
            "total_flags": 0,
            "awaiting_review": 0,
            "high_risk_unresolved": 0,
            "clearance_rate": 0,
        }}
    
    # Query Firestore for runs owned by this user.
    #
    # Deliberately no order_by: an equality-only filter is served by Firestore's
    # automatic single-field index, so this needs no composite index. Ordering on
    # created_at here would also silently drop older documents that predate the
    # top-level created_at mirror, since Firestore excludes documents missing the
    # sort field. Sorting happens in Python below instead.
    try:
        query = (
            store._collection
            .where("owner_uid", "==", current_user.uid)
            .limit(100)
        )

        docs = list(query.stream())
        runs = []

        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue

            # The public payload is nested under "public"; several fields are also
            # mirrored to the top level by FirestoreRunStore.save(). Read the
            # mirror first and fall back to the nested copy so runs written before
            # the mirror existed still resolve.
            public = data.get("public") or {}
            public_run = public.get("run") or {}

            # _public_summary() writes flat *_count keys, not a counts_by_risk dict.
            summary = data.get("summary") or public.get("summary") or {}

            runs.append({
                "run_id": data.get("run_id") or public_run.get("run_id"),
                "script_title": data.get("script_title") or public_run.get("script_title"),
                "created_at": data.get("created_at") or public_run.get("created_at"),
                "updated_at": data.get("updated_at") or public_run.get("updated_at"),
                "overall_status": (
                    data.get("overall_status")
                    or public_run.get("overall_status")
                    or "pending"
                ),
                "entity_count": summary.get("total_entities") or 0,
                "high_count": summary.get("high_risk_count") or 0,
                "caution_count": summary.get("caution_count") or 0,
                "clear_count": summary.get("clear_count") or 0,
                "cleared_for_export": bool(
                    data.get("cleared_for_export")
                    or public.get("cleared_for_export")
                ),
            })

        # Newest first. Runs without a timestamp sort last rather than crashing.
        runs.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        
        logger.info("Dashboard query returned %d run(s) for uid=%s", len(runs), current_user.uid)

        # Compute aggregate stats
        total_scripts = len(runs)
        total_flags = sum(r["entity_count"] for r in runs)
        awaiting_review = sum(1 for r in runs if r["overall_status"] == "pending")
        high_risk_unresolved = sum(r["high_count"] for r in runs if not r["cleared_for_export"])
        cleared = sum(1 for r in runs if r["overall_status"] == "approved")
        clearance_rate = (cleared / total_scripts * 100) if total_scripts else 0
        
        return {
            "runs": runs,
            "stats": {
                "total_scripts": total_scripts,
                "total_flags": total_flags,
                "awaiting_review": awaiting_review,
                "high_risk_unresolved": high_risk_unresolved,
                "clearance_rate": round(clearance_rate),
            },
        }
        
    except Exception as exc:
        logger.exception("Failed to list user clearance runs")
        raise HTTPException(
            status_code=500,
            detail="Could not load your clearance runs.",
        ) from exc


def _report_filename(run: ClearanceRunResponse) -> str:
    """Build a safe download filename from the script title."""
    raw = run.script_title or run.run_id or "clearance_report"
    stem = Path(raw).stem  # drop a trailing .pdf/.txt from the original upload
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem).strip("_")
    return f"{safe or 'clearance_report'}_scriptclearAI.pdf"


@app.get("/clearance/{run_id}/pdf")
async def download_clearance_report(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Stream the clearance report PDF for a run the caller owns.

    Serves the stored artifact from Cloud Storage using the gs:// pointer held on
    the run record, so the bytes the user downloads are the exact ones that were
    hashed at sign-off. If the pointer is missing (run predates report storage,
    or the upload failed) the PDF is rebuilt on demand so the button still works.
    """
    stored = _load_owned_run(run_id, current_user)
    run = stored.public.run
    disposition = f'attachment; filename="{_report_filename(run)}"'

    report_url = run.report_file_url
    if report_url:
        try:
            pdf_bytes = _storage_download_from_gs_url(report_url)
        except Exception:
            logger.exception(
                "Could not fetch stored report for run %s (%s); regenerating",
                run_id,
                report_url,
            )
        else:
            # These are the exact bytes that were hashed at sign-off, so the
            # recorded digest is a valid reference for verifying this copy.
            headers = {
                "Content-Disposition": disposition,
                "X-Report-Source": "storage",
            }
            if run.report_hash:
                headers["X-Report-SHA256"] = run.report_hash
            logger.info("Served stored report for run %s from %s", run_id, report_url)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers=headers,
            )

    # Fallback: rebuild from the persisted run so the download never dead-ends.
    try:
        from api.report_generator import generate_report_pdf

        pdf_bytes = generate_report_pdf(stored.public)
    except Exception as exc:
        logger.exception("On-demand report generation failed for run %s", run_id)
        raise HTTPException(
            status_code=500,
            detail="The clearance report could not be produced.",
        ) from exc

    # Deliberately no X-Report-SHA256 here. generate_report_pdf() stamps the
    # current timestamp into the header band, so a rebuilt PDF never reproduces
    # the bytes that were hashed at sign-off. Returning the stored digest
    # alongside these bytes would make a legitimate report look tampered with.
    # X-Report-Source lets the client say "regenerated copy — verification
    # unavailable" instead of reporting a false mismatch.
    logger.info(
        "Served regenerated report for run %s; copy is not hash-verifiable", run_id
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": disposition,
            "X-Report-Source": "regenerated",
        },
    )


@app.post(
    "/clearance/{run_id}/entities/{entity_id}/decision",
    response_model=ClearanceResponse,
)
async def record_entity_decision_endpoint(
    run_id: str,
    entity_id: str,
    body: EntityDecisionRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ClearanceResponse:
    """Record a human entity decision using the server-side review workflow."""
    stored = _load_owned_run(run_id, current_user)
    try:
        updated = apply_entity_decision(
            stored,
            entity_id=entity_id,
            decision=body.decision,
            reviewer_uid=current_user.uid,
            reviewer_name=current_user.name,
            comment=body.comment,
        )
    except ValueError as exc:
        logger.info("Entity decision rejected: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="This decision could not be recorded for the requested entity.",
        ) from exc

    get_run_store().save(updated)
    updated = _maybe_generate_report(updated, reviewer_name=current_user.name or current_user.uid)
    get_run_store().save(updated)
    return updated.public


@app.post("/clearance/{run_id}/decision", response_model=ClearanceResponse)
async def record_overall_decision_endpoint(
    run_id: str,
    body: OverallDecisionRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ClearanceResponse:
    """Record a run-level decision and re-evaluate clearance on the server."""
    if body.decision == ReviewDecision.NEEDS_REVIEW:
        raise HTTPException(
            status_code=400,
            detail="Overall decision must be approved or blocked.",
        )

    stored = _load_owned_run(run_id, current_user)
    try:
        updated = apply_overall_decision(
            stored,
            decision=body.decision,
            reviewer_uid=current_user.uid,
            reviewer_name=current_user.name,
            comment=body.comment,
        )
    except ValueError as exc:
        logger.info("Overall decision rejected: %s", exc)
        raise HTTPException(
            status_code=409,
            detail="This run cannot be approved until required entity reviews are complete.",
        ) from exc

    get_run_store().save(updated)
    updated = _maybe_generate_report(updated, reviewer_name=current_user.name or current_user.uid)
    get_run_store().save(updated)
    return updated.public
