"""
tests/conftest.py

pytest configuration and shared fixtures for Agentic Cinema tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Force a local store and high rate limit before any API import.
os.environ["CLEARANCE_STORE"] = "memory"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load .env file for all tests."""
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}")
    else:
        print(f"WARNING: .env file not found at {env_path}")


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def test_scripts_dir(project_root) -> Path:
    """Return the test scripts directory."""
    return project_root / "tests" / "scripts"


@pytest.fixture(scope="session")
def test_screenplay_text(test_scripts_dir) -> str:
    """Load the basic test screenplay."""
    path = test_scripts_dir / "test_screenplay.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def integration_screenplay_text(test_scripts_dir) -> str:
    """Load the integration test screenplay."""
    path = test_scripts_dir / "integration_screenplay.txt"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def requires_api_key():
    """Skip test if API key not configured."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        pytest.skip("API key not configured (GOOGLE_API_KEY or GEMINI_API_KEY)")


@pytest.fixture
def requires_parallel_key():
    """Skip test if Parallel API key not configured."""
    if not os.getenv("PARALLEL_API_KEY"):
        pytest.skip("Parallel API key not configured (PARALLEL_API_KEY)")