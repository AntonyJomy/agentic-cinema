"""
agents/model_config.py

Shared Gemini model selection for all agents.

Override with GEMINI_MODEL in .env (e.g. gemini-2.5-flash, gemini-2.0-flash).
Default prefers a widely available Flash model to reduce 503 high-demand failures
seen with newer preview models.
"""
from __future__ import annotations

import os


DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
