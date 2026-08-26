"""
api/settings.py

Environment-backed API configuration.

Keep secrets and runtime limits here so endpoints do not read os.environ
ad hoc. Authentication is intentionally not configured — see api/auth.py.
"""
from __future__ import annotations

import os

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value > 0 else default


def environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_production() -> bool:
    return environment() in {"production", "prod"}


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def max_upload_bytes() -> int:
    return _env_int("MAX_UPLOAD_SIZE_MB", 20) * 1024 * 1024


def max_pdf_pages() -> int:
    return _env_int("MAX_PDF_PAGES", 200)


def max_script_chars() -> int:
    return _env_int("MAX_SCRIPT_CHARS", 1_000_000)


def rate_limit_per_minute() -> int:
    return _env_int("RATE_LIMIT_PER_MINUTE", 30)


def clearance_store_backend() -> str:
    return os.getenv("CLEARANCE_STORE", "auto").strip().lower()


def firestore_project() -> str:
    return os.getenv("FIRESTORE_PROJECT", "script-clearance-hackathon").strip()


def firestore_database() -> str:
    return os.getenv("FIRESTORE_DATABASE", "script-clearance-db").strip()
