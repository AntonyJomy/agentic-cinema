"""
api/report_pdf.py

Build a downloadable clearance PDF from a stored ClearanceResponse.
Uses PyMuPDF (already a project dependency).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO

import pymupdf

from api.schemas import ClearanceResponse


def _safe_filename(title: str | None, run_id: str) -> str:
    raw = (title or "").strip() or run_id or "screenplay"
    base = re.sub(r"\.(pdf|txt)$", "", raw, flags=re.I)
    base = re.sub(r"[^\w.\-]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_") or "screenplay"
    return f"{base}_scriptclearAI.pdf"


def _wrap(text: str, width: int = 92) -> list[str]:
    words = (text or "").replace("\n", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class _PdfBuilder:
    def __init__(self) -> None:
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=595, height=842)  # A4
        self.y = 48
        self.margin = 48
        self.width = 595 - 96

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=595, height=842)
        self.y = 48

    def _ensure(self, need: float) -> None:
        if self.y + need > 842 - 48:
            self._new_page()

    def heading(self, text: str, size: float = 18) -> None:
        self._ensure(size + 16)
        self.page.insert_text(
            (self.margin, self.y),
            text,
            fontsize=size,
            fontname="helv",
            color=(0.12, 0.12, 0.12),
        )
        self.y += size + 10

    def subheading(self, text: str) -> None:
        self._ensure(26)
        self.page.insert_text(
            (self.margin, self.y),
            text.upper(),
            fontsize=10,
            fontname="helv",
            color=(0.55, 0.4, 0.12),
        )
        self.y += 16

    def line(self, text: str, size: float = 10, color=(0.2, 0.2, 0.2)) -> None:
        for chunk in _wrap(text, width=95):
            self._ensure(size + 6)
            self.page.insert_text(
                (self.margin, self.y),
                chunk,
                fontsize=size,
                fontname="helv",
                color=color,
            )
            self.y += size + 4

    def spacer(self, amount: float = 10) -> None:
        self.y += amount

    def rule(self) -> None:
        self._ensure(12)
        self.page.draw_line(
            pymupdf.Point(self.margin, self.y),
            pymupdf.Point(self.margin + self.width, self.y),
            color=(0.82, 0.82, 0.82),
            width=0.6,
        )
        self.y += 12

    def bytes(self) -> bytes:
        buffer = BytesIO()
        self.doc.save(buffer)
        self.doc.close()
        return buffer.getvalue()


def build_clearance_pdf(response: ClearanceResponse) -> tuple[bytes, str]:
    """Return (pdf_bytes, download_filename) for a clearance package."""
    run = response.run
    summary = response.summary or {}
    gatekeeper = response.gatekeeper or {}
    builder = _PdfBuilder()

    builder.heading("ScriptClear AI", size=20)
    builder.line("E&O Clearance Report", size=11, color=(0.45, 0.45, 0.45))
    builder.spacer(4)
    builder.rule()

    title = run.script_title or "Untitled screenplay"
    builder.heading(title, size=16)
    builder.line(f"Run ID: {run.run_id}")
    builder.line(f"Status: {run.overall_status}")
    builder.line(f"Created: {run.created_at}")
    builder.line(f"Updated: {run.updated_at}")
    if run.reviewed_by:
        builder.line(f"Reviewed by: {run.reviewed_by}")
    builder.line(
        f"Cleared for export: {'Yes' if response.cleared_for_export else 'No'}"
    )
    builder.line(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    builder.spacer(6)
    builder.rule()

    if gatekeeper:
        builder.subheading("Gatekeeper")
        builder.line(f"Status: {gatekeeper.get('status') or '—'}")
        builder.line(f"Reason: {gatekeeper.get('reason') or '—'}")
        if gatekeeper.get("message"):
            builder.line(str(gatekeeper["message"]))
        builder.spacer(4)

    if summary:
        builder.subheading("Summary")
        if summary.get("overall_summary"):
            builder.line(str(summary["overall_summary"]))
        builder.line(
            "Clear / Caution / High risk: "
            f"{summary.get('clear_count', 0)} / "
            f"{summary.get('caution_count', 0)} / "
            f"{summary.get('high_risk_count', 0)}"
        )
        builder.spacer(4)

    recommendations = response.recommendations or []
    if recommendations:
        builder.subheading("Recommendations")
        for item in recommendations[:12]:
            builder.line(f"• {item}")
        builder.spacer(4)

    builder.subheading("Entities")
    entities = run.entities or []
    if not entities:
        builder.line("No entities recorded.")
    else:
        for entity in entities:
            name = entity.name or "Untitled entity"
            risk = entity.risk_level or "—"
            status = entity.status or "—"
            builder.line(f"{name}  ·  {risk}  ·  {status}", size=10)
            if entity.research_finding:
                builder.line(str(entity.research_finding), size=9, color=(0.35, 0.35, 0.35))
            page = (entity.location or {}).get("page_number")
            if page:
                builder.line(f"Page {page}", size=9, color=(0.45, 0.45, 0.45))
            builder.spacer(4)

    builder.spacer(8)
    builder.rule()
    builder.line(
        "This document was generated by ScriptClear AI. Findings are provisional. "
        "Human legal review is required before production, distribution, or insurance "
        "submission. This report is not legal advice.",
        size=8,
        color=(0.4, 0.4, 0.4),
    )

    filename = _safe_filename(run.script_title, run.run_id)
    return builder.bytes(), filename
