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
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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
from gatekeeper.cloud_storage import upload_screenplay  # noqa: E402
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
    
    # Upload file to Cloud Storage for persistence
    # Generate a run_id for the file (we'll use a temporary one since no clearance run exists yet)
    import uuid
    temp_run_id = f"upload-{uuid.uuid4().hex[:8]}"
    
    try:
        file_url = upload_screenplay(raw, filename, temp_run_id)
    except Exception as exc:
        logger.warning(f"Failed to upload file to Cloud Storage: {exc}")
        file_url = None  # Continue without file storage if GCS is unavailable
    
    return ExtractScriptResponse(
        script=script,
        filename=filename,
        page_count=page_count,
        script_title=title,
        # Include file_url in the response for tracking
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
    
    # Upload original file to Cloud Storage
    # Note: We don't have the raw file bytes here since they were already consumed
    # In a production system, you'd pass the file bytes through or re-upload
    # For now, we'll just note that the file should be stored during /extract-script
    
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
    return updated.public
