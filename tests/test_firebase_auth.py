"""
tests/test_firebase_auth.py

Unit tests for gatekeeper.firebase_auth helpers.
Google-auth / Firebase Admin are mocked so no real credentials are required.
"""
import os
import sys
from unittest.mock import patch

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from gatekeeper.firebase_auth import (
    AuthenticationError,
    AuthorizationError,
    verify_id_token,
    verify_legal_reviewer,
)


def test_verify_id_token_via_google_auth():
    decoded = {
        "sub": "user-123",
        "email": "user@example.com",
        "aud": "script-clearance-hackathon",
    }

    with (
        patch("gatekeeper.firebase_auth.firebase_project_id", return_value="script-clearance-hackathon"),
        patch("gatekeeper.firebase_auth.firebase_ready", return_value=False),
        patch(
            "gatekeeper.firebase_auth.google_id_token.verify_firebase_token",
            return_value=decoded,
        ) as mock_verify,
    ):
        result = verify_id_token("valid-token")

    mock_verify.assert_called_once()
    assert result["uid"] == "user-123"
    assert result["email"] == "user@example.com"


def test_legal_reviewer_passes():
    decoded = {
        "uid": "reviewer-123",
        "email": "reviewer@example.com",
        "legal_reviewer": True,
    }

    with (
        patch("gatekeeper.firebase_auth.firebase_project_id", return_value="demo"),
        patch("gatekeeper.firebase_auth.firebase_ready", return_value=False),
        patch(
            "gatekeeper.firebase_auth.google_id_token.verify_firebase_token",
            return_value=decoded,
        ),
    ):
        result = verify_legal_reviewer("valid-token")

    assert result == decoded


def test_user_without_role_is_rejected():
    decoded = {
        "uid": "user-456",
        "email": "user@example.com",
    }

    with (
        patch("gatekeeper.firebase_auth.firebase_project_id", return_value="demo"),
        patch("gatekeeper.firebase_auth.firebase_ready", return_value=False),
        patch(
            "gatekeeper.firebase_auth.google_id_token.verify_firebase_token",
            return_value=decoded,
        ),
    ):
        with pytest.raises(AuthorizationError):
            verify_legal_reviewer("valid-token")


def test_invalid_firebase_token():
    with (
        patch("gatekeeper.firebase_auth.firebase_project_id", return_value="demo"),
        patch("gatekeeper.firebase_auth.firebase_ready", return_value=False),
        patch(
            "gatekeeper.firebase_auth.google_id_token.verify_firebase_token",
            side_effect=ValueError("bad token"),
        ),
    ):
        with pytest.raises(AuthenticationError):
            verify_legal_reviewer("invalid-token")


def test_missing_token():
    with pytest.raises(AuthenticationError):
        verify_legal_reviewer("")


def test_missing_project_id():
    with (
        patch("gatekeeper.firebase_auth.firebase_project_id", return_value=""),
        patch("gatekeeper.firebase_auth.firebase_ready", return_value=False),
    ):
        with pytest.raises(AuthenticationError):
            verify_id_token("some-token")
