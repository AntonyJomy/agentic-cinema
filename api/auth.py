"""
api/auth.py

Request identity for the clearance API.

THIS MODULE IS A DEVELOPMENT STUB. It does not authenticate anyone.
Firebase Authentication / login / signup is not implemented.

TODO(firebase-auth): Replace get_current_user() with Firebase ID token
verification. Endpoints should keep depending on this function so that
swap does not require rewriting route handlers.

Future flow:
    Authorization: Bearer <Firebase ID Token>
        → firebase_admin.auth.verify_id_token
        → CurrentUser(uid, email, name, role from claims)
        → existing API endpoints
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request


# Isolated development-only identity. Not a security boundary.
DEV_USER_ID = "dev-user"


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated (or development) caller identity.

    Endpoints must take identity from this object. Never from request bodies.
    """

    uid: str
    email: str
    name: str
    role: str
    is_development_identity: bool = False


DEV_USER = CurrentUser(
    uid=DEV_USER_ID,
    email="developer@local",
    name="Development User",
    role="legal_reviewer",
    is_development_identity=True,
)


def get_current_user(request: Request) -> CurrentUser:
    """Return the caller identity for this request.

    Development: always returns DEV_USER. Request headers and body are ignored
    for identity (uid, reviewer name, role, approval identity).

    TODO(firebase-auth): Read Authorization: Bearer <id_token>, verify with
    Firebase, map uid/email/name and the legal_reviewer claim onto CurrentUser.
    Reject missing/invalid tokens in production. The `request` argument is
    accepted now so that swap does not change the FastAPI dependency signature.
    """
    _ = request
    return DEV_USER
