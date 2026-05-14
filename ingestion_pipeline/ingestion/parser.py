"""
parser.py
---------
Handles raw file → clean-text extraction.

Strategy
--------
1.  If a LLAMA_CLOUD_API_KEY env-var is set, use LlamaParse (cloud) for
    high-fidelity PDF extraction (preserves tables, charts, multi-column
    layouts).
2.  Fallback: PyMuPDF (fitz) for PDFs and plain read() for text files.

The module is intentionally thin – it just returns raw extracted text
(possibly paginated) so that cleaner.py and chunker.py can operate on a
consistent interface.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result type:  list of (page_number_or_None, raw_text)
PagedText = List[Tuple[Optional[int], str]]
# ─────────────────────────────────────────────────────────────────────────────


def _parse_pdf_llama(path: Path) -> PagedText:
    """Use LlamaParse cloud API for high-fidelity extraction."""
    try:
        from llama_parse import LlamaParse  # type: ignore
    except ImportError:
        raise ImportError(
            "llama-parse is not installed. "
            "Run: pip install llama-parse"
        )

    api_key = os.environ["LLAMA_CLOUD_API_KEY"]
    parser = LlamaParse(
        api_key=api_key,
        result_type="markdown",   # preserves tables as markdown
        verbose=False,
        language="en",
    )

    logger.info("[LlamaParse] Parsing %s …", path.name)
    documents = parser.load_data(str(path))

    pages: PagedText = []
    for i, doc in enumerate(documents, start=1):
        pages.append((i, doc.text))
    return pages


def _parse_pdf_pymupdf(path: Path) -> PagedText:
    """Fallback: PyMuPDF (fitz) page-by-page extraction."""
    try:
        import fitz  # type: ignore  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is not installed. "
            "Run: pip install pymupdf"
        )

    logger.info("[PyMuPDF] Parsing %s …", path.name)
    pages: PagedText = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append((page.number + 1, text))
    return pages


def _parse_text_file(path: Path) -> PagedText:
    """Plain-text / markdown / log files."""
    logger.info("[TextParser] Reading %s …", path.name)
    text = path.read_text(encoding="utf-8", errors="replace")
    return [(None, text)]


def _parse_ticket_json(path: Path) -> PagedText:
    """
    Mock ticket format expected:
      {"id": "TICK-001", "title": "...", "description": "...",
       "resolution": "...", "tags": [...]}
    """
    import json

    logger.info("[TicketParser] Reading %s …", path.name)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Support both a single ticket and a list of tickets
    tickets = data if isinstance(data, list) else [data]
    pages: PagedText = []
    for i, ticket in enumerate(tickets, start=1):
        parts = []
        if ticket.get("id"):
            parts.append(f"TICKET ID: {ticket['id']}")
        if ticket.get("title"):
            parts.append(f"TITLE: {ticket['title']}")
        if ticket.get("description"):
            parts.append(f"DESCRIPTION:\n{ticket['description']}")
        if ticket.get("resolution"):
            parts.append(f"RESOLUTION:\n{ticket['resolution']}")
        if ticket.get("tags"):
            parts.append(f"TAGS: {', '.join(ticket['tags'])}")
        pages.append((i, "\n\n".join(parts)))
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".log", ".json"}


def parse_file(path: Path, force_fallback: bool = False) -> PagedText:
    """
    Parse a single file and return a list of (page_number, raw_text) tuples.

    Parameters
    ----------
    path           : Path to the file.
    force_fallback : If True, skip LlamaParse even if the API key is set.
                     Useful for testing without cloud credits.

    Returns
    -------
    PagedText – list of (Optional[int], str) pairs.
    """
    suffix = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if suffix == ".pdf":
        llama_key = os.environ.get("LLAMA_CLOUD_API_KEY", "").strip()
        if llama_key and not force_fallback:
            try:
                return _parse_pdf_llama(path)
            except Exception as exc:
                logger.warning(
                    "LlamaParse failed (%s). Falling back to PyMuPDF.", exc
                )
        return _parse_pdf_pymupdf(path)

    if suffix in {".txt", ".md", ".log"}:
        return _parse_text_file(path)

    if suffix == ".json":
        return _parse_ticket_json(path)

    raise ValueError(
        f"Unsupported file type: '{suffix}'. "
        f"Supported: {SUPPORTED_EXTENSIONS}"
    )
