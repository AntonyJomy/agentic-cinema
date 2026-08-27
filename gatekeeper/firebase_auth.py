"""
gatekeeper/firebase_auth.py

Firebase ID-token verification and role checks.

Verification uses Google's public certs via google-auth
(google.oauth2.id_token.verify_firebase_token), so a service account / ADC
is not required for login. Firebase Admin is an optional enhancement when
credentials are available (e.g. revoked-token checks).
"""
from __future__ import annotations

import logging

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from gatekeeper.firebase_app import firebase_project_id, firebase_ready

logger = logging.getLogger("agentic_cinema.firebase_auth")


class AuthenticationError(Exception):
    """Raised when Firebase authentication fails."""


class AuthorizationError(Exception):
    """Raised when the authenticated user lacks the required role."""


def _normalize_claims(decoded: dict) -> dict:
    claims = dict(decoded)
    if not claims.get("uid") and claims.get("sub"):
        claims["uid"] = claims["sub"]
    return claims


def _verify_with_google_auth(id_token: str, project_id: str) -> dict:
    decoded = google_id_token.verify_firebase_token(
        id_token,
        google_requests.Request(),
        audience=project_id,
    )
    if not isinstance(decoded, dict):
        raise AuthenticationError("Invalid Firebase ID token")
    return _normalize_claims(decoded)


def _verify_with_admin_sdk(id_token: str) -> dict | None:
    """Return decoded claims when Admin SDK is ready; otherwise None."""
    if not firebase_ready():
        return None
    try:
        from firebase_admin import auth

        return _normalize_claims(auth.verify_id_token(id_token))
    except Exception as exc:
        logger.debug("Firebase Admin verify failed; falling back: %s", exc)
        return None


def verify_id_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return the decoded claims.

    Raises AuthenticationError for missing/invalid tokens.
    """
    if not id_token:
        raise AuthenticationError("Firebase ID token is required")

    project_id = firebase_project_id()
    if not project_id:
        raise AuthenticationError(
            "Firebase project id is not configured. "
            "Set FIREBASE_PROJECT_ID or FIRESTORE_PROJECT."
        )

    admin_claims = _verify_with_admin_sdk(id_token)
    if admin_claims is not None:
        return admin_claims

    try:
        return _verify_with_google_auth(id_token, project_id)
    except AuthenticationError:
        raise
    except Exception as exc:
        raise AuthenticationError("Invalid Firebase ID token") from exc


def verify_legal_reviewer(id_token: str) -> dict:
    """Verify a Firebase ID token and require the legal_reviewer claim.

    Returns the decoded token when the user is authenticated and authorized.
    Raises AuthenticationError for missing/invalid tokens.
    Raises AuthorizationError when the legal_reviewer claim is absent or false.
    """
    decoded_token = verify_id_token(id_token)

    if decoded_token.get("legal_reviewer") is not True:
        raise AuthorizationError(
            "User does not have the legal_reviewer role"
        )

    return decoded_token
