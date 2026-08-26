"""
api/pdf_text.py

Extract plain text from screenplay PDF bytes using PyMuPDF.
"""
from __future__ import annotations

import pymupdf

from api.settings import max_pdf_pages


class PdfExtractionError(Exception):
    """Raised when PDF text extraction fails or yields no usable text."""


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    """Return (full_text, page_count) extracted from a PDF.

    Raises PdfExtractionError when the file is not a readable PDF,
    exceeds MAX_PDF_PAGES, or contains no extractable text.
    """
    if not pdf_bytes:
        raise PdfExtractionError("PDF file is empty")

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PdfExtractionError("Could not open PDF file") from exc

    try:
        page_count = len(doc)
        if page_count == 0:
            raise PdfExtractionError("PDF has no pages")

        limit = max_pdf_pages()
        if page_count > limit:
            raise PdfExtractionError(
                f"PDF exceeds the maximum of {limit} pages."
            )

        parts: list[str] = []
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text() or ""
            parts.append(f"\n\n--- Page {page_num + 1} ---\n{text}")

        full_text = "".join(parts).strip()
        if not full_text:
            raise PdfExtractionError(
                "No extractable text found in PDF (it may be scanned/image-only)"
            )
        return full_text, page_count
    finally:
        doc.close()
