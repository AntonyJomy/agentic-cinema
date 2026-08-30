"""
api/settings.py

Environment-backed API configuration.

Keep secrets and runtime limits here so endpoints do not read os.environ
ad hoc. Authentication mode lives here; token verification is in api/auth.py.
"""
from __future__ import annotations

import os

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower()


def is_production() -> bool:
    return environment() in {"production", "prod"}


def auth_mode() -> str:
    """Return 'development' (optional auth) or 'firebase' (required)."""
    raw = os.getenv("AUTH_MODE", "").strip().lower()
    if raw in {"development", "dev", "stub"}:
        return "development"
    if raw in {"firebase", "required", "production"}:
        return "firebase"
    return "firebase" if is_production() else "development"


def auth_require_legal_reviewer() -> bool:
    """When true, Firebase users need custom claim legal_reviewer=true."""
    return _env_bool("AUTH_REQUIRE_LEGAL_REVIEWER", False)


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
