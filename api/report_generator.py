"""
api/report_generator.py

Generates a clearance report PDF for a completed clearance run.

Uses PyMuPDF (pymupdf) to build a clean, readable PDF that contains:
  - Run title and metadata header
  - Executive summary
  - Entity findings table: name, type, risk level, triggered rule,
    evidence URLs, legal decision, and sign-off reviewer

Call generate_report_pdf(stored) -> bytes.
The caller is responsible for uploading the bytes and recording the URL.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

import pymupdf  # PyMuPDF >= 1.24

from api.schemas import ClearanceEntityResponse, ClearanceRunResponse, ClearanceResponse


# ---------------------------------------------------------------------------
# Layout constants (all measurements in points; 1 pt = 1/72 inch)
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = 595, 842  # A4
MARGIN = 50
CONTENT_W = PAGE_W - 2 * MARGIN

# Fonts (built-in PDF base-14)
FONT_REGULAR = "helv"
FONT_BOLD = "hebo"

# Colours (r, g, b) in 0-1 range
CLR_BLACK = (0.0, 0.0, 0.0)
CLR_DARK_GREY = (0.2, 0.2, 0.2)
CLR_MID_GREY = (0.4, 0.4, 0.4)
CLR_LIGHT_GREY = (0.85, 0.85, 0.85)
CLR_WHITE = (1.0, 1.0, 1.0)
CLR_HEADER_BG = (0.08, 0.08, 0.15)  # very dark navy
CLR_HIGH_RISK = (0.75, 0.1, 0.1)
CLR_CAUTION = (0.7, 0.45, 0.0)
CLR_CLEAR = (0.1, 0.5, 0.1)
CLR_BLOCKED = (0.6, 0.0, 0.0)
CLR_APPROVED = (0.0, 0.45, 0.2)

RISK_COLOURS = {
    "high_risk": CLR_HIGH_RISK,
    "caution": CLR_CAUTION,
    "clear": CLR_CLEAR,
}
DECISION_COLOURS = {
    "cleared": CLR_APPROVED,
    "blocked": CLR_BLOCKED,
    "overridden": CLR_CAUTION,
    "flagged": CLR_MID_GREY,
}


def _risk_colour(risk_level: str | None) -> tuple:
    return RISK_COLOURS.get(risk_level or "", CLR_DARK_GREY)


def _decision_colour(status: str | None) -> tuple:
    return DECISION_COLOURS.get(status or "", CLR_DARK_GREY)


# ---------------------------------------------------------------------------
# Low-level drawing helpers
# ---------------------------------------------------------------------------

def _draw_rect_filled(page, x0: float, y0: float, x1: float, y1: float, colour: tuple) -> None:
    rect = pymupdf.Rect(x0, y0, x1, y1)
    page.draw_rect(rect, color=None, fill=colour)


def _text(page, x: float, y: float, text: str, fontsize: float,
          colour: tuple = CLR_BLACK, bold: bool = False, align: int = 0) -> None:
    """Insert a single line of text at (x, y) — top-left origin."""
    font = FONT_BOLD if bold else FONT_REGULAR
    page.insert_text(
        pymupdf.Point(x, y),
        text,
        fontname=font,
        fontsize=fontsize,
        color=colour,
    )


def _wrapped_text(page, x: float, y: float, text: str, fontsize: float,
                  max_width: float, colour: tuple = CLR_BLACK,
                  bold: bool = False, line_height: float | None = None) -> float:
    """
    Insert text wrapped to max_width. Returns the y position after the last line.
    """
    font = FONT_BOLD if bold else FONT_REGULAR
    lh = line_height or (fontsize * 1.4)
    rect = pymupdf.Rect(x, y - fontsize, x + max_width, y + 5000)
    page.insert_textbox(
        rect,
        text,
        fontname=font,
        fontsize=fontsize,
        color=colour,
        align=0,
    )
    # Estimate how many lines were used
    approx_chars_per_line = max(1, int(max_width / (fontsize * 0.55)))
    lines = max(1, -(-len(text) // approx_chars_per_line))  # ceiling div
    return y + lines * lh


def _hline(page, y: float, colour: tuple = CLR_LIGHT_GREY, width: float = 0.5) -> None:
    page.draw_line(
        pymupdf.Point(MARGIN, y),
        pymupdf.Point(PAGE_W - MARGIN, y),
        color=colour,
        width=width,
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header_block(page, run: ClearanceRunResponse, generated_at: str) -> float:
    """Draw the report header band. Returns y after the block."""
    # Background band
    _draw_rect_filled(page, 0, 0, PAGE_W, 80, CLR_HEADER_BG)

    _text(page, MARGIN, 28, "CLEARANCE REPORT", fontsize=16, colour=CLR_WHITE, bold=True)
    title = run.script_title or "Untitled Screenplay"
    _text(page, MARGIN, 50, title[:80], fontsize=11, colour=(0.8, 0.8, 0.85))
    _text(page, MARGIN, 68, f"Run ID: {run.run_id}", fontsize=7.5, colour=(0.6, 0.6, 0.7))

    # Status badge (top-right)
    status_label = run.overall_status.upper()
    badge_x = PAGE_W - MARGIN - 80
    badge_colour = CLR_APPROVED if run.overall_status == "approved" else CLR_BLOCKED
    _draw_rect_filled(page, badge_x - 6, 14, badge_x + 74, 36, badge_colour)
    _text(page, badge_x, 29, status_label, fontsize=9, colour=CLR_WHITE, bold=True)

    y = 95
    # Meta row
    meta_parts = []
    if run.reviewed_by:
        meta_parts.append(f"Reviewed by: {run.reviewed_by}")
    if run.reviewed_at:
        meta_parts.append(f"Signed off: {run.reviewed_at[:10]}")
    meta_parts.append(f"Generated: {generated_at}")
    _text(page, MARGIN, y, "  |  ".join(meta_parts), fontsize=8, colour=CLR_MID_GREY)
    _hline(page, y + 6)
    return y + 18


def _summary_block(page, y: float, response: ClearanceResponse) -> float:
    """Draw the executive summary and statistics. Returns y after the block."""
    _text(page, MARGIN, y, "Executive Summary", fontsize=12, bold=True)
    y += 14

    summary = response.summary or {}
    overall = (summary.get("overall_summary") or "No summary available.").strip()
    y = _wrapped_text(page, MARGIN, y, overall, fontsize=9, max_width=CONTENT_W, colour=CLR_DARK_GREY)
    y += 8

    # Statistics row
    clear_c = summary.get("clear_count", 0)
    caution_c = summary.get("caution_count", 0)
    high_c = summary.get("high_risk_count", 0)
    total = summary.get("total_entities", 0)

    stats = [
        ("Total entities", str(total), CLR_DARK_GREY),
        ("Clear", str(clear_c), CLR_CLEAR),
        ("Caution", str(caution_c), CLR_CAUTION),
        ("High risk", str(high_c), CLR_HIGH_RISK),
    ]
    box_w = CONTENT_W / len(stats)
    for i, (label, val, col) in enumerate(stats):
        bx = MARGIN + i * box_w
        _draw_rect_filled(page, bx + 2, y, bx + box_w - 4, y + 32, CLR_LIGHT_GREY)
        _text(page, bx + 8, y + 13, val, fontsize=14, colour=col, bold=True)
        _text(page, bx + 8, y + 27, label, fontsize=7.5, colour=CLR_MID_GREY)

    y += 42
    _hline(page, y)
    return y + 10


def _entity_block(page, y: float, entity: ClearanceEntityResponse, index: int) -> float:
    """
    Draw one entity card. Returns the y position after the card.
    Starts a new page if there isn't enough vertical space.
    """
    CARD_MIN_H = 72
    if y + CARD_MIN_H > PAGE_H - MARGIN:
        return None  # Caller must insert page break

    # Alternating row background
    if index % 2 == 0:
        _draw_rect_filled(page, MARGIN, y - 4, PAGE_W - MARGIN, y + CARD_MIN_H, (0.97, 0.97, 0.97))

    # Entity name + type
    _text(page, MARGIN + 4, y + 11, entity.name[:60], fontsize=10, bold=True)
    _text(page, MARGIN + 4, y + 23,
          f"{entity.entity_type}  ·  {entity.risk_category}",
          fontsize=7.5, colour=CLR_MID_GREY)

    # Risk badge
    risk_label = (entity.risk_level or "unknown").upper().replace("_", " ")
    risk_col = _risk_colour(entity.risk_level)
    rx = PAGE_W - MARGIN - 100
    _draw_rect_filled(page, rx, y + 2, rx + 90, y + 18, risk_col)
    _text(page, rx + 4, y + 14, risk_label, fontsize=8, colour=CLR_WHITE, bold=True)

    # Decision badge
    dec_label = (entity.status or "pending").upper()
    dec_col = _decision_colour(entity.status)
    _draw_rect_filled(page, rx, y + 22, rx + 90, y + 38, dec_col)
    _text(page, rx + 4, y + 35, dec_label, fontsize=8, colour=CLR_WHITE, bold=True)

    # Triggered rule
    rule = entity.triggered_rule or "—"
    _text(page, MARGIN + 4, y + 37, f"Rule: {rule[:80]}", fontsize=7.5, colour=CLR_DARK_GREY)

    # Evidence URLs (up to 2)
    if entity.evidence:
        urls = [e.get("url") or e.get("source_url", "") for e in entity.evidence[:2]]
        urls = [u for u in urls if u]
        url_text = "  ·  ".join(u[:60] for u in urls) if urls else "—"
        _text(page, MARGIN + 4, y + 50, f"Evidence: {url_text}", fontsize=7, colour=CLR_MID_GREY)

    # Legal decision + reviewer
    legal_dec = entity.legal_decision or "—"
    _text(page, MARGIN + 4, y + 62,
          f"Legal decision: {legal_dec}",
          fontsize=7.5, colour=CLR_DARK_GREY)

    _hline(page, y + CARD_MIN_H - 2, colour=(0.9, 0.9, 0.9), width=0.3)
    return y + CARD_MIN_H


def _footer(page, page_num: int, total_pages: int) -> None:
    y = PAGE_H - 22
    _hline(page, y - 4, colour=CLR_LIGHT_GREY)
    _text(page, MARGIN, y + 8,
          "CONFIDENTIAL — FOR INTERNAL CLEARANCE USE ONLY",
          fontsize=7, colour=CLR_MID_GREY)
    _text(page, PAGE_W - MARGIN - 60, y + 8,
          f"Page {page_num} of {total_pages}",
          fontsize=7, colour=CLR_MID_GREY)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_report_pdf(response: ClearanceResponse) -> bytes:
    """
    Generate a clearance report PDF from a completed ClearanceResponse.

    Returns the PDF as raw bytes ready for upload to Cloud Storage.
    """
    run = response.run
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    doc = pymupdf.open()

    def _new_page() -> tuple[pymupdf.Page, float]:
        p = doc.new_page(width=PAGE_W, height=PAGE_H)
        return p, MARGIN

    # ---- Page 1: header + summary + start of entities ----
    page, _ = _new_page()
    y = _header_block(page, run, generated_at)
    y = _summary_block(page, y, response)

    # Section heading for entities
    _text(page, MARGIN, y, "Findings", fontsize=12, bold=True)
    y += 14

    entities = sorted(
        run.entities,
        key=lambda e: {"high_risk": 0, "caution": 1, "clear": 2}.get(e.risk_level or "", 3),
    )

    for i, entity in enumerate(entities):
        result = _entity_block(page, y, entity, i)
        if result is None:
            # Need a new page
            _footer(page, doc.page_count, 0)  # placeholder, updated below
            page, y = _new_page()
            y = MARGIN + 10
            result = _entity_block(page, y, entity, i)
        y = result

    # Gatekeeper summary at the end
    y += 8
    if y + 60 > PAGE_H - MARGIN:
        _footer(page, doc.page_count, 0)
        page, y = _new_page()
        y = MARGIN + 10

    gatekeeper = response.gatekeeper or {}
    _hline(page, y)
    y += 12
    _text(page, MARGIN, y, "Gatekeeper Decision", fontsize=11, bold=True)
    y += 14
    status_str = gatekeeper.get("status", "unknown").upper()
    status_col = CLR_APPROVED if gatekeeper.get("cleared_for_export") else CLR_BLOCKED
    _text(page, MARGIN, y, status_str, fontsize=10, colour=status_col, bold=True)
    y += 13
    gate_msg = gatekeeper.get("message") or ""
    if gate_msg:
        _wrapped_text(page, MARGIN, y, gate_msg, fontsize=9,
                      max_width=CONTENT_W, colour=CLR_DARK_GREY)

    # Back-fill correct page numbers
    total = doc.page_count
    for pg_num, pg in enumerate(doc, start=1):
        _footer(pg, pg_num, total)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
