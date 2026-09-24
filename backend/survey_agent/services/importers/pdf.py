"""PDF form import: extract text and fillable field names, then let the AI build questions."""
from __future__ import annotations

import pymupdf

from ...errors import APIError

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PAGES = 60


def extract_pdf(pdf_bytes: bytes) -> tuple[str, list[str]]:
    if not pdf_bytes:
        raise APIError("The uploaded file is empty", code="invalid_pdf")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise APIError("PDFs must be 10 MB or smaller", code="invalid_pdf")
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several exception types for corrupt files
        raise APIError("That file isn't a readable PDF", code="invalid_pdf") from exc
    with doc:
        if doc.needs_pass:
            raise APIError("Password-protected PDFs aren't supported", code="invalid_pdf")
        if doc.page_count > MAX_PAGES:
            raise APIError(f"PDFs are limited to {MAX_PAGES} pages", code="invalid_pdf")
        text_parts: list[str] = []
        fields: list[str] = []
        for page in doc:
            text_parts.append(page.get_text())
            for widget in page.widgets() or []:
                if widget.field_name and widget.field_name not in fields:
                    fields.append(widget.field_name)
    text = "\n".join(text_parts).strip()
    if not text and not fields:
        raise APIError(
            "No text found in that PDF. Scanned images aren't supported yet.",
            code="invalid_pdf",
        )
    return text, fields
