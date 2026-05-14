"""
pipeline.py
-----------
Main entry-point for the Data Ingestion & Processing pipeline.

Public function
---------------
    ingest_directory(
        input_dir   : str | Path,
        output_path : str | Path | None,
        chunk_size  : int,
        overlap     : int,
        extra_meta  : dict | None,
        force_fallback : bool,
    ) -> list[dict]

The function:
  1. Walks `input_dir` recursively and locates all supported files.
  2. Parses each file  (LlamaParse → PyMuPDF fallback for PDFs).
  3. Cleans the raw text.
  4. Splits into overlapping, sentence-aligned chunks.
  5. Returns a **standardised list of JSON-serialisable dicts** – one per
     chunk – that downstream components (vector indexer, graph builder)
     can directly consume.
  6. Optionally writes the list to `output_path` as a .jsonl file.

Usage
-----
    from ingestion.pipeline import ingest_directory

    chunks = ingest_directory(
        input_dir  = "data/raw",
        output_path= "data/processed/chunks.jsonl",
    )
    print(f"Produced {len(chunks)} chunks.")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .chunker import chunk_pages
from .cleaner import clean_document
from .models import ChunkDocument, IngestionReport, SourceType
from .parser import parse_file, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Extension → SourceType mapping
# ─────────────────────────────────────────────────────────────────────────────
_EXT_TO_SOURCE: Dict[str, SourceType] = {
    ".pdf" : SourceType.PDF,
    ".txt" : SourceType.TXT,
    ".md"  : SourceType.MD,
    ".log" : SourceType.LOG,
    ".json": SourceType.TICKET,   # assumed to be mock tickets
}


def _discover_files(directory: Path) -> List[Path]:
    """Return all supported files under `directory`, sorted for determinism."""
    files = [
        p for p in sorted(directory.rglob("*"))
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    logger.info("Discovered %d file(s) in '%s'.", len(files), directory)
    return files


def _source_type_for(path: Path) -> SourceType:
    return _EXT_TO_SOURCE.get(path.suffix.lower(), SourceType.UNKNOWN)


def _build_extra_meta(path: Path, base_dir: Path) -> Dict[str, Any]:
    """Derive metadata from the file's location within the input directory."""
    try:
        rel = path.relative_to(base_dir)
    except ValueError:
        rel = path
    return {
        "filename"   : path.name,
        "relative_path": str(rel),
        "file_size_bytes": path.stat().st_size,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────────────────────────────────────

def ingest_directory(
    input_dir      : Union[str, Path],
    output_path    : Optional[Union[str, Path]] = None,
    chunk_size     : int                         = 512,
    overlap        : int                         = 64,
    extra_meta     : Optional[Dict[str, Any]]    = None,
    force_fallback : bool                        = False,
) -> List[Dict[str, Any]]:
    """
    Ingest all supported files in `input_dir` and return a list of
    standardised chunk dicts.

    Parameters
    ----------
    input_dir      : Directory containing raw enterprise documents.
    output_path    : If provided, write the chunks as JSONL to this path.
    chunk_size     : Target tokens per chunk (default 512).
    overlap        : Token overlap between adjacent chunks (default 64).
    extra_meta     : Additional metadata to attach to every chunk
                     (e.g. {"project": "Phoenix", "env": "prod"}).
    force_fallback : Skip LlamaParse even if API key is present.

    Returns
    -------
    List of dicts – each dict is a ChunkDocument serialised via
    `model.to_dict()`.  This list is the contract with downstream
    components.
    """
    input_dir  = Path(input_dir)
    extra_meta = extra_meta or {}
    started_at = datetime.now(tz=timezone.utc).isoformat()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    files        = _discover_files(input_dir)
    all_chunks   : List[ChunkDocument] = []
    errors       : List[str] = []
    files_ok     = 0

    for file_path in files:
        logger.info("Processing: %s", file_path.name)
        try:
            # 1. Parse
            paged_text = parse_file(file_path, force_fallback=force_fallback)

            # 2. Clean
            cleaned_pages = clean_document(paged_text)
            if not cleaned_pages:
                logger.warning("No content extracted from %s – skipping.", file_path.name)
                continue

            # 3. Chunk
            file_meta   = _build_extra_meta(file_path, input_dir)
            merged_meta = {**file_meta, **extra_meta}
            chunks = chunk_pages(
                pages       = cleaned_pages,
                source_file = str(file_path),
                source_type = _source_type_for(file_path),
                extra_meta  = merged_meta,
                chunk_size  = chunk_size,
                overlap     = overlap,
            )
            all_chunks.extend(chunks)
            files_ok += 1
            logger.info(
                "  └─ %d chunk(s) from %s", len(chunks), file_path.name
            )

        except Exception as exc:
            msg = f"Failed to process '{file_path}': {exc}"
            logger.error(msg)
            errors.append(msg)

    finished_at = datetime.now(tz=timezone.utc).isoformat()

    # ── Build report ──────────────────────────────────────────────────────
    report = IngestionReport(
        started_at      = started_at,
        finished_at     = finished_at,
        files_attempted = len(files),
        files_succeeded = files_ok,
        files_failed    = len(files) - files_ok,
        total_chunks    = len(all_chunks),
        errors          = errors,
        output_path     = str(output_path) if output_path else None,
    )

    logger.info(
        "Ingestion complete. Files: %d/%d succeeded | Chunks: %d | Errors: %d",
        files_ok, len(files), len(all_chunks), len(errors),
    )

    # ── Serialise ─────────────────────────────────────────────────────────
    serialised: List[Dict[str, Any]] = [c.to_dict() for c in all_chunks]

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write chunks as JSONL
        with open(output_path, "w", encoding="utf-8") as f:
            for item in serialised:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # Write sidecar report
        report_path = output_path.with_suffix(".report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info("Wrote %d chunks → %s", len(serialised), output_path)
        logger.info("Wrote report → %s", report_path)

    return serialised


# ─────────────────────────────────────────────────────────────────────────────
# CLI convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level  = logging.INFO,
        format = "%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )

    ap = argparse.ArgumentParser(
        description="Enterprise Knowledge Copilot – Data Ingestion Pipeline"
    )
    ap.add_argument("input_dir",  help="Directory containing raw documents")
    ap.add_argument(
        "--output", "-o",
        default=None,
        help="Path for output JSONL file (default: input_dir/chunks.jsonl)",
    )
    ap.add_argument("--chunk-size", type=int, default=512)
    ap.add_argument("--overlap",    type=int, default=64)
    ap.add_argument(
        "--fallback", action="store_true",
        help="Force PyMuPDF fallback even if LLAMA_CLOUD_API_KEY is set",
    )
    args = ap.parse_args()

    output = args.output or str(Path(args.input_dir) / "chunks.jsonl")

    chunks = ingest_directory(
        input_dir      = args.input_dir,
        output_path    = output,
        chunk_size     = args.chunk_size,
        overlap        = args.overlap,
        force_fallback = args.fallback,
    )
    print(f"\n✅  Done – {len(chunks)} chunk(s) written to {output}")
    sys.exit(0)
