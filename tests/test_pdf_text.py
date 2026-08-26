"""
tests/test_pdf_text.py

Unit tests for PDF screenplay text extraction and /extract-script.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["CLEARANCE_STORE"] = "memory"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ.setdefault("ENVIRONMENT", "development")

import pytest

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient

from api.main import app
from api.pdf_text import PdfExtractionError, extract_text_from_pdf

client = TestClient(app)
PDF_PATH = project_root / "tests" / "scripts" / "Screenplay_1.pdf"
TXT_PATH = project_root / "tests" / "scripts" / "test_screenplay.txt"


@pytest.fixture(scope="module")
def sample_pdf_bytes() -> bytes:
    if not PDF_PATH.exists():
        pytest.skip(f"Missing sample PDF: {PDF_PATH}")
    return PDF_PATH.read_bytes()


def test_extract_text_from_pdf_returns_content(sample_pdf_bytes: bytes):
    text, page_count = extract_text_from_pdf(sample_pdf_bytes)
    assert page_count >= 1
    assert len(text.strip()) > 50
    assert "--- Page 1 ---" in text


def test_extract_text_from_pdf_rejects_empty():
    with pytest.raises(PdfExtractionError):
        extract_text_from_pdf(b"")


def test_extract_text_from_pdf_rejects_garbage():
    with pytest.raises(PdfExtractionError):
        extract_text_from_pdf(b"not-a-pdf")


def test_extract_text_from_pdf_rejects_too_many_pages(sample_pdf_bytes: bytes, monkeypatch):
    monkeypatch.setattr("api.pdf_text.max_pdf_pages", lambda: 0)
    with pytest.raises(PdfExtractionError, match="maximum"):
        extract_text_from_pdf(sample_pdf_bytes)


def test_extract_script_endpoint_pdf(sample_pdf_bytes: bytes):
    response = client.post(
        "/extract-script",
        files={"file": ("Screenplay_1.pdf", sample_pdf_bytes, "application/pdf")},
        data={"script_title": "PDF Upload Test"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "Screenplay_1.pdf"
    assert payload["page_count"] >= 1
    assert len(payload["script"].strip()) > 50
    assert payload["script_title"] == "PDF Upload Test"


def test_extract_script_endpoint_txt():
    if not TXT_PATH.exists():
        pytest.skip(f"Missing sample TXT: {TXT_PATH}")
    raw = TXT_PATH.read_bytes()
    response = client.post(
        "/extract-script",
        files={"file": ("test_screenplay.txt", raw, "text/plain")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "test_screenplay.txt"
    assert payload["page_count"] is None
    assert "INT." in payload["script"] or len(payload["script"]) > 20


def test_extract_script_rejects_unsupported_type():
    response = client.post(
        "/extract-script",
        files={"file": ("notes.docx", b"fake", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]
