"""
gatekeeper/firebase_auth.py

Standalone Firebase authentication/authorization helpers for role checks.
"""
from firebase_admin import auth


class AuthenticationError(Exception):
    """Raised when Firebase authentication fails."""


class AuthorizationError(Exception):
    """Raised when the authenticated user lacks the required role."""


def verify_legal_reviewer(id_token: str) -> dict:
    """Verify a Firebase ID token and require the legal_reviewer claim.

    Returns the decoded token when the user is authenticated and authorized.
    Raises AuthenticationError for missing/invalid tokens.
    Raises AuthorizationError when the legal_reviewer claim is absent or false.
    """
    if not id_token:
        raise AuthenticationError("Firebase ID token is required")

    try:
        decoded_token = auth.verify_id_token(id_token)
    except Exception as exc:
        raise AuthenticationError("Invalid Firebase ID token") from exc

    if decoded_token.get("legal_reviewer") is not True:
        raise AuthorizationError(
            "User does not have the legal_reviewer role"
        )

    return decoded_token
