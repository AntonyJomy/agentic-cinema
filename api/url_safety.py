"""
api/url_safety.py

Allow only http(s) evidence URLs in API responses and stored citations.
"""
from __future__ import annotations

from urllib.parse import urlparse


def is_safe_http_url(value: object) -> bool:
    """True when value is an absolute http or https URL with a host."""
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    text = value.strip()
    if not text or text.lower().startswith(("javascript:", "data:", "file:", "vbscript:")):
        return False
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return True


def require_http_url(value: object) -> str:
    """Return a stripped http(s) URL or raise ValueError."""
    text = str(value).strip() if value is not None else ""
    if not is_safe_http_url(text):
        raise ValueError("URL must use http or https")
    return text


def sanitize_evidence_items(items: list | None) -> list[dict]:
    """Drop evidence entries whose source_url is missing or not http(s)."""
    safe: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = item.get("source_url")
        if url and not is_safe_http_url(url):
            continue
        if url:
            safe.append(
                {
                    "source_url": str(url).strip(),
                    "summary": item.get("summary") or "",
                    "retrieved_via": item.get("retrieved_via") or "parallel",
                }
            )
        elif item.get("summary"):
            safe.append(
                {
                    "source_url": None,
                    "summary": item.get("summary") or "",
                    "retrieved_via": item.get("retrieved_via") or "parallel",
                }
            )
    return safe
