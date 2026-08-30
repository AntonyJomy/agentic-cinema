"""
tests/test_api_auth.py

Unit tests for api.auth.get_current_user.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from api.auth import DEV_USER, get_current_user  # noqa: E402


def _request(authorization: str | None = None):
    request = MagicMock()
    headers = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    request.headers.get = headers.get
    return request


def test_development_mode_returns_dev_user_without_token():
    with patch("api.auth.auth_mode", return_value="development"):
        user = get_current_user(_request())
    assert user == DEV_USER


def test_firebase_mode_requires_token():
    with patch("api.auth.auth_mode", return_value="firebase"):
        with pytest.raises(HTTPException) as exc:
            get_current_user(_request())
    assert exc.value.status_code == 401


def test_valid_bearer_maps_to_current_user():
    decoded = {
        "uid": "google-uid-1",
        "email": "reviewer@studio.com",
        "name": "Ada Reviewer",
        "legal_reviewer": True,
    }
    with (
        patch("api.auth.auth_mode", return_value="firebase"),
        patch("api.auth.auth_require_legal_reviewer", return_value=False),
        patch("api.auth.verify_id_token", return_value=decoded),
    ):
        user = get_current_user(_request("Bearer good-token"))

    assert user.uid == "google-uid-1"
    assert user.email == "reviewer@studio.com"
    assert user.name == "Ada Reviewer"
    assert user.role == "legal_reviewer"
    assert user.is_development_identity is False


def test_invalid_bearer_returns_401():
    from gatekeeper.firebase_auth import AuthenticationError

    with (
        patch("api.auth.auth_mode", return_value="firebase"),
        patch("api.auth.auth_require_legal_reviewer", return_value=False),
        patch(
            "api.auth.verify_id_token",
            side_effect=AuthenticationError("Invalid Firebase ID token"),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            get_current_user(_request("Bearer bad-token"))
    assert exc.value.status_code == 401
