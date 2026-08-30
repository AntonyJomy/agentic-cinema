"""
api/auth.py

Request identity for the clearance API.

Auth modes (AUTH_MODE):
  - development: missing Bearer → DEV_USER; present Bearer → verify Firebase
  - firebase: Bearer Firebase ID token required on every request

Token verification uses Google public certs (no service account required).
Optional Firebase Admin credentials enable Admin SDK verification when present.

Optional:
  AUTH_REQUIRE_LEGAL_REVIEWER=true requires custom claim legal_reviewer=true.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from api.settings import auth_mode, auth_require_legal_reviewer
from gatekeeper.firebase_auth import (
    AuthenticationError,
    AuthorizationError,
    verify_id_token,
    verify_legal_reviewer,
)


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


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization") or ""
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _user_from_claims(decoded: dict) -> CurrentUser:
    uid = str(decoded.get("uid") or decoded.get("sub") or "").strip()
    if not uid:
        raise AuthenticationError("Firebase token is missing uid")

    email = str(decoded.get("email") or "").strip()
    name = (
        str(decoded.get("name") or "").strip()
        or (email.split("@", 1)[0] if email else "")
        or uid
    )
    role = (
        "legal_reviewer"
        if decoded.get("legal_reviewer") is True
        else "authenticated"
    )
    return CurrentUser(
        uid=uid,
        email=email or f"{uid}@users.noreply",
        name=name,
        role=role,
        is_development_identity=False,
    )


def get_current_user(request: Request) -> CurrentUser:
    """Return the caller identity for this request."""
    token = _bearer_token(request)
    mode = auth_mode()

    if token:
        try:
            if auth_require_legal_reviewer():
                decoded = verify_legal_reviewer(token)
            else:
                decoded = verify_id_token(token)
            return _user_from_claims(decoded)
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail="Authentication failed",
            ) from exc

    if mode == "development":
        return DEV_USER

    raise HTTPException(
        status_code=401,
        detail=(
            "Authentication required. Sign in with Google and send "
            "an Authorization Bearer Firebase ID token."
        ),
    )
