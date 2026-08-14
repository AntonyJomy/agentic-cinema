"""
api/main.py

FastAPI backend for the Agentic Cinema clearance pipeline.

Exposes POST /clearance which invokes the existing orchestrator pipeline.
POST /clearance/stream streams real-time agent progress as NDJSON lines.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

from api.response_builder import build_clearance_response  # noqa: E402
from api.schemas import ClearanceRequest, ClearanceResponse  # noqa: E402
from orchestrator import run_clearance_pipeline  # noqa: E402

logger = logging.getLogger("agentic_cinema.api")

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

cors_origins = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app = FastAPI(
    title="Agentic Cinema Clearance API",
    version="0.1.0",
    description="HTTP API for the screenplay E&O clearance agent pipeline.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _validate_clearance_request(request: ClearanceRequest) -> str:
    script = request.script.strip()
    if not script:
        raise HTTPException(status_code=400, detail="Script text must not be empty")

    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        logger.error("Missing GOOGLE_API_KEY or GEMINI_API_KEY")
        raise HTTPException(
            status_code=503,
            detail="Clearance service is not configured. API keys are missing on the server.",
        )
    return script


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/clearance", response_model=ClearanceResponse)
async def run_clearance(request: ClearanceRequest) -> ClearanceResponse:
    """Run the full clearance pipeline for a screenplay."""
    script = _validate_clearance_request(request)

    try:
        pipeline_result = await run_clearance_pipeline(
            script,
            screenplay_path="<api>",
            user_id="api",
        )
    except RuntimeError as exc:
        logger.warning("Pipeline stopped: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Clearance pipeline failed")
        raise HTTPException(
            status_code=500,
            detail="Clearance pipeline failed. Check server logs for details.",
        ) from exc

    if request.script_title:
        pipeline_result.grounded_entities = pipeline_result.grounded_entities.model_copy(
            update={"script_title": request.script_title.strip()}
        )

    return build_clearance_response(
        pipeline_result,
        script_title=request.script_title,
    )


@app.post("/clearance/stream")
async def run_clearance_stream(request: ClearanceRequest) -> StreamingResponse:
    """Stream clearance pipeline progress as newline-delimited JSON events."""
    script = _validate_clearance_request(request)

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def on_progress(progress_event) -> None:
            await queue.put({"type": "progress", **progress_event.to_dict()})

        async def run_pipeline() -> None:
            try:
                pipeline_result = await run_clearance_pipeline(
                    script,
                    screenplay_path="<api>",
                    user_id="api",
                    on_progress=on_progress,
                )

                if request.script_title:
                    pipeline_result.grounded_entities = (
                        pipeline_result.grounded_entities.model_copy(
                            update={"script_title": request.script_title.strip()}
                        )
                    )

                response = build_clearance_response(
                    pipeline_result,
                    script_title=request.script_title,
                )
                await queue.put(
                    {
                        "type": "complete",
                        "duration_seconds": pipeline_result.duration_seconds,
                        "result": response.model_dump(mode="json"),
                    }
                )
            except RuntimeError as exc:
                await queue.put({"type": "error", "status": 422, "detail": str(exc)})
            except Exception as exc:
                logger.exception("Streaming clearance pipeline failed")
                await queue.put(
                    {
                        "type": "error",
                        "status": 500,
                        "detail": "Clearance pipeline failed. Check server logs for details.",
                        "message": str(exc),
                    }
                )
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
