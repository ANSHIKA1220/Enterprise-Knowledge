"""
cleaner.py
----------
Transforms raw extracted text (from parser.py) into clean, normalised
text that is safe to embed and index.

Pipeline
--------
1.  Decode / normalise unicode (ligatures, smart quotes, etc.)
2.  Remove boilerplate patterns (headers, footers, page numbers, URLs
    that add no semantic value, repeated whitespace)
3.  Detect and tag content type (plain text, markdown table, code block)
4.  Return a CleanedPage dataclass consumed by chunker.py
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from .models import ContentType


# ─────────────────────────────────────────────────────────────────────────────
# Compiled regex patterns (module-level for performance)
# ─────────────────────────────────────────────────────────────────────────────

# Repeated whitespace / blank lines
_RE_MULTI_BLANK   = re.compile(r"\n{3,}")
_RE_MULTI_SPACE   = re.compile(r"[ \t]{2,}")

# Page numbers like "Page 3 of 12" or just "- 3 -"
_RE_PAGE_NUM      = re.compile(
    r"(\bPage\s+\d+\s+of\s+\d+\b|\s*[-–]\s*\d+\s*[-–]\s*)", re.I
)

# Lone header/footer lines that are purely decorative (e.g. "──────────────")
_RE_DIVIDER       = re.compile(r"^[-─═*=_]{5,}\s*$", re.M)

# Control characters (except newline / tab)
_RE_CONTROL       = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Markdown / LlamaParse table indicator
_RE_TABLE_ROW     = re.compile(r"^\|.+\|", re.M)

# Code fences
_RE_CODE_FENCE    = re.compile(r"^```", re.M)

# Excessive punctuation runs (e.g. ".......................")
_RE_PUNCT_RUN     = re.compile(r"([.!?,;])\1{4,}")


# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CleanedPage:
    text        : str
    page_number : Optional[int]
    content_type: ContentType = ContentType.TEXT
    char_count  : int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_unicode(text: str) -> str:
    """NFKC normalisation collapses ligatures, smart quotes, etc."""
    return unicodedata.normalize("NFKC", text)


def _remove_boilerplate(text: str) -> str:
    text = _RE_PAGE_NUM.sub(" ", text)
    text = _RE_DIVIDER.sub("", text)
    text = _RE_CONTROL.sub("", text)
    text = _RE_PUNCT_RUN.sub(r"\1\1\1", text)  # collapse to max 3
    return text


def _normalise_whitespace(text: str) -> str:
    text = _RE_MULTI_SPACE.sub(" ", text)
    text = _RE_MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def _detect_content_type(text: str) -> ContentType:
    has_table = bool(_RE_TABLE_ROW.search(text))
    has_code  = bool(_RE_CODE_FENCE.search(text))
    if has_table and has_code:
        return ContentType.MIXED
    if has_table:
        return ContentType.TABLE
    if has_code:
        return ContentType.CODE
    return ContentType.TEXT


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def clean_page(raw_text: str, page_number: Optional[int] = None) -> CleanedPage:
    """
    Clean a single page / section of raw extracted text.

    Parameters
    ----------
    raw_text    : Raw text as returned by parser.py.
    page_number : Original page number (or None).

    Returns
    -------
    CleanedPage with normalised text and inferred ContentType.
    """
    text = _normalise_unicode(raw_text)
    text = _remove_boilerplate(text)
    text = _normalise_whitespace(text)
    content_type = _detect_content_type(text)
    return CleanedPage(text=text, page_number=page_number, content_type=content_type)


def clean_document(pages: list[tuple[Optional[int], str]]) -> list[CleanedPage]:
    """
    Clean an entire document (list of (page_num, raw_text) pairs).

    Parameters
    ----------
    pages : Output of parser.parse_file().

    Returns
    -------
    List of CleanedPage objects, empty pages filtered out.
    """
    cleaned = []
    for page_num, raw in pages:
        cp = clean_page(raw, page_num)
        if cp.text:   # drop pages that become empty after cleaning
            cleaned.append(cp)
    return cleaned
