"""
gatekeeper/firebase_app.py

Lazy Firebase Admin SDK initialization (optional).

ID-token verification does not require Admin credentials — see
gatekeeper.firebase_auth. Admin SDK is used when ADC / a service-account
JSON is available.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

logger = logging.getLogger("agentic_cinema.firebase")

_init_attempted = False
_init_error: str | None = None


def firebase_project_id() -> str:
    return (
        os.getenv("FIREBASE_PROJECT_ID")
        or os.getenv("FIRESTORE_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or ""
    ).strip()


def _adc_path() -> Path | None:
    explicit = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if explicit:
        return Path(explicit)
    appdata = os.getenv("APPDATA")
    if appdata:
        win = Path(appdata) / "gcloud" / "application_default_credentials.json"
        if win.is_file():
            return win
    unix = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    if unix.is_file():
        return unix
    return None


def _running_on_gcp() -> bool:
    """Cloud Run / Cloud Functions / App Engine attach ADC via the metadata server."""
    return bool(
        os.getenv("K_SERVICE")  # Cloud Run
        or os.getenv("FUNCTION_TARGET")  # Cloud Functions
        or os.getenv("GAE_ENV")  # App Engine
        or os.getenv("GCE_METADATA_HOST")
    )


def admin_credentials_available() -> bool:
    """True when a service-account/ADC file exists, or we are on GCP with metadata ADC."""
    path = _adc_path()
    if path and path.is_file():
        return True
    return _running_on_gcp()


def ensure_firebase_app() -> firebase_admin.App:
    """Initialize the default Firebase app once using ADC / service account.

    Raises RuntimeError when credentials or project id are missing/invalid.
    """
    global _init_attempted, _init_error

    if firebase_admin._apps:
        return firebase_admin.get_app()

    if _init_attempted and _init_error:
        raise RuntimeError(_init_error)

    _init_attempted = True
    project_id = firebase_project_id()
    if not project_id:
        _init_error = (
            "Firebase project id is not configured. "
            "Set FIREBASE_PROJECT_ID or FIRESTORE_PROJECT."
        )
        raise RuntimeError(_init_error)

    # Prefer an explicit file when present; otherwise use Application Default
    # Credentials (local ADC file OR Cloud Run / GCE metadata server).
    try:
        cred_path = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
        if cred_path and os.path.isfile(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(cred, {"projectId": project_id})
        logger.info("Firebase Admin initialized for project %s", project_id)
        return app
    except Exception as exc:
        _init_error = f"Firebase Admin initialization failed: {exc}"
        logger.warning(
            "Firebase Admin unavailable (token verify will use google-auth): %s",
            exc,
        )
        raise RuntimeError(_init_error) from exc


def firebase_ready() -> bool:
    """Return True when Firebase Admin can verify ID tokens."""
    try:
        ensure_firebase_app()
        return True
    except Exception:
        return False
