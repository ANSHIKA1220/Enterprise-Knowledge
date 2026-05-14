"""
models.py
---------
Pydantic schemas for the standardised output produced by the ingestion
pipeline.  Every downstream component (vector DB indexer, graph builder,
etc.) consumes a list of `ChunkDocument` objects.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    PDF    = "pdf"
    TXT    = "txt"
    MD     = "markdown"
    TICKET = "ticket"
    WIKI   = "wiki"
    LOG    = "log"
    UNKNOWN = "unknown"


class ContentType(str, Enum):
    TEXT  = "text"
    TABLE = "table"
    CODE  = "code"
    MIXED = "mixed"


class ChunkDocument(BaseModel):
    """
    The canonical unit produced by the ingestion pipeline.

    Fields
    ------
    chunk_id        : Stable, deterministic UUID (sha256 of source + text).
    text            : Cleaned, ready-to-embed text content.
    metadata        : Arbitrary key-value bag for filters / graph edges.
    source_file     : Absolute or relative path of the original file.
    source_type     : Enum – pdf | txt | markdown | ticket | wiki | log.
    content_type    : text | table | code | mixed.
    chunk_index     : Zero-based position of this chunk inside its document.
    total_chunks    : Total chunks produced from the parent document.
    page_number     : Page (PDFs) or section number; None if not applicable.
    char_start      : Character offset of chunk start inside cleaned document.
    char_end        : Character offset of chunk end.
    token_estimate  : Rough token count (chars / 4).
    ingested_at     : ISO-8601 timestamp of ingestion.
    """

    chunk_id      : str = Field(default_factory=lambda: str(uuid.uuid4()))
    text          : str
    metadata      : Dict[str, Any] = Field(default_factory=dict)
    source_file   : str
    source_type   : SourceType = SourceType.UNKNOWN
    content_type  : ContentType = ContentType.TEXT
    chunk_index   : int = 0
    total_chunks  : int = 1
    page_number   : Optional[int] = None
    char_start    : int = 0
    char_end      : int = 0
    token_estimate: int = 0
    ingested_at   : str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------ #
    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Chunk text must not be empty.")
        return v

    # ------------------------------------------------------------------ #
    def compute_stable_id(self) -> "ChunkDocument":
        """
        Recompute chunk_id as a deterministic sha256 hash so identical
        chunks from repeat ingestions always get the same ID (idempotent
        upserts into the vector DB).
        """
        raw = f"{self.source_file}::{self.chunk_index}::{self.text}"
        self.chunk_id = hashlib.sha256(raw.encode()).hexdigest()
        return self

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class IngestionReport(BaseModel):
    """Summary emitted at the end of a pipeline run."""
    run_id           : str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at       : str
    finished_at      : str
    files_attempted  : int = 0
    files_succeeded  : int = 0
    files_failed     : int = 0
    total_chunks     : int = 0
    errors           : List[str] = Field(default_factory=list)
    output_path      : Optional[str] = None
