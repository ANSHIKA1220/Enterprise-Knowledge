"""
chunker.py
----------
Splits cleaned text into overlapping chunks optimised for both:
  • Vector DB ingestion  (semantic similarity search via embeddings)
  • Graph DB ingestion   (entity / relationship extraction via Neo4j)

Strategy
--------
1.  Sentence-aware sliding window:  chunks stay close to `chunk_size`
    tokens but always break on sentence boundaries to preserve semantic
    coherence.
2.  Overlap:  the last `overlap` tokens of chunk N are prepended to
    chunk N+1 so that no context is lost at chunk boundaries.
3.  Table / code preservation:  if a CleanedPage has ContentType TABLE
    or CODE, the entire block is kept as a single chunk (never split mid-
    table or mid-fence).

Token approximation: 1 token ≈ 4 chars (GPT tokeniser heuristic) – good
enough for chunking; actual token counts are verified at embed time.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .cleaner import CleanedPage
from .models import ChunkDocument, ContentType, SourceType

# ─────────────────────────────────────────────────────────────────────────────
# Defaults (can be overridden per call)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_CHUNK_SIZE    = 512   # target tokens per chunk
DEFAULT_OVERLAP       = 64    # token overlap between consecutive chunks
CHARS_PER_TOKEN       = 4     # approximation

# Sentence boundary: end of sentence followed by whitespace
_RE_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences, keeping the delimiter attached."""
    parts = _RE_SENTENCE_BOUNDARY.split(text)
    # Re-attach trailing whitespace stripped by split
    return [p.strip() for p in parts if p.strip()]


def _sliding_window_chunks(
    text: str,
    chunk_size: int,
    overlap: int,
) -> List[tuple[str, int, int]]:
    """
    Yield (chunk_text, char_start, char_end) tuples via a sentence-aware
    sliding window.
    """
    sentences    = _split_sentences(text)
    chunks: List[tuple[str, int, int]] = []
    current_sents: List[str] = []
    current_tokens = 0
    char_cursor    = 0

    def flush(sents: List[str], start: int) -> tuple[str, int, int]:
        chunk_text = " ".join(sents)
        return (chunk_text, start, start + len(chunk_text))

    for sent in sentences:
        sent_tokens = _tokens(sent)
        if current_tokens + sent_tokens > chunk_size and current_sents:
            chunk_text, cs, ce = flush(current_sents, char_cursor)
            chunks.append((chunk_text, cs, ce))
            char_cursor = ce

            # Keep overlap: pop sentences from the front until we're under
            # the overlap budget
            while current_sents and _tokens(" ".join(current_sents)) > overlap:
                current_sents.pop(0)
            current_tokens = _tokens(" ".join(current_sents)) if current_sents else 0

        current_sents.append(sent)
        current_tokens += sent_tokens

    # Flush remainder
    if current_sents:
        chunk_text, cs, ce = flush(current_sents, char_cursor)
        chunks.append((chunk_text, cs, ce))

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def chunk_pages(
    pages        : List[CleanedPage],
    source_file  : str,
    source_type  : SourceType        = SourceType.UNKNOWN,
    extra_meta   : Optional[dict]    = None,
    chunk_size   : int               = DEFAULT_CHUNK_SIZE,
    overlap      : int               = DEFAULT_OVERLAP,
) -> List[ChunkDocument]:
    """
    Convert a list of CleanedPage objects into ChunkDocument objects.

    Parameters
    ----------
    pages       : Output of cleaner.clean_document().
    source_file : Original file path (stored in metadata).
    source_type : SourceType enum value.
    extra_meta  : Optional dict of additional metadata key-values
                  (e.g. {"project": "ITSM", "department": "DevOps"}).
    chunk_size  : Target chunk size in tokens.
    overlap     : Token overlap between consecutive chunks.

    Returns
    -------
    List[ChunkDocument]  – ready to be serialised to JSON and fed into
                           the vector / graph indexers.
    """
    extra_meta = extra_meta or {}
    all_chunks: List[ChunkDocument] = []
    global_idx = 0

    for page in pages:
        # ── Tables and code blocks: keep as single chunks ─────────────────
        if page.content_type in (ContentType.TABLE, ContentType.CODE):
            doc = ChunkDocument(
                text         = page.text,
                source_file  = source_file,
                source_type  = source_type,
                content_type = page.content_type,
                chunk_index  = global_idx,
                total_chunks = -1,   # patched below
                page_number  = page.page_number,
                char_start   = 0,
                char_end     = len(page.text),
                token_estimate = _tokens(page.text),
                metadata     = {
                    "page_number" : page.page_number,
                    "content_type": page.content_type.value,
                    **extra_meta,
                },
            ).compute_stable_id()
            all_chunks.append(doc)
            global_idx += 1
            continue

        # ── Plain text: sliding window ─────────────────────────────────────
        raw_chunks = _sliding_window_chunks(page.text, chunk_size, overlap)
        for chunk_text, cs, ce in raw_chunks:
            doc = ChunkDocument(
                text         = chunk_text,
                source_file  = source_file,
                source_type  = source_type,
                content_type = page.content_type,
                chunk_index  = global_idx,
                total_chunks = -1,   # patched below
                page_number  = page.page_number,
                char_start   = cs,
                char_end     = ce,
                token_estimate = _tokens(chunk_text),
                metadata     = {
                    "page_number" : page.page_number,
                    "content_type": page.content_type.value,
                    **extra_meta,
                },
            ).compute_stable_id()
            all_chunks.append(doc)
            global_idx += 1

    # Patch total_chunks now that we know the final count
    total = len(all_chunks)
    for doc in all_chunks:
        doc.total_chunks = total

    return all_chunks
