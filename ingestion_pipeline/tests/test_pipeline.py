"""
tests/test_pipeline.py
----------------------
Unit + integration tests for the Data Ingestion & Processing pipeline.

Run with:
    pytest tests/ -v
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# ── Module under test ────────────────────────────────────────────────────────
from ingestion.cleaner  import clean_page, clean_document
from ingestion.chunker  import chunk_pages, _sliding_window_chunks, _tokens
from ingestion.models   import ChunkDocument, ContentType, SourceType
from ingestion.parser   import parse_file
from ingestion.pipeline import ingest_directory


# ═══════════════════════════════════════════════════════════════════════════
# CLEANER TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestCleaner:

    def test_removes_page_numbers(self):
        raw = "Some content.\nPage 3 of 10\nMore content."
        cp  = clean_page(raw)
        assert "Page 3 of 10" not in cp.text

    def test_removes_control_chars(self):
        raw = "Hello\x00World\x1fEnd"
        cp  = clean_page(raw)
        assert "\x00" not in cp.text
        assert "\x1f" not in cp.text

    def test_collapses_blank_lines(self):
        raw = "A\n\n\n\n\nB"
        cp  = clean_page(raw)
        assert "\n\n\n" not in cp.text

    def test_detects_table_content(self):
        raw = "| Column A | Column B |\n|----------|----------|\n| Val 1    | Val 2    |"
        cp  = clean_page(raw)
        assert cp.content_type == ContentType.TABLE

    def test_detects_code_content(self):
        raw = "Some explanation.\n```python\nprint('hello')\n```"
        cp  = clean_page(raw)
        assert cp.content_type == ContentType.CODE

    def test_plain_text_content_type(self):
        raw = "This is a plain sentence about Kubernetes networking."
        cp  = clean_page(raw)
        assert cp.content_type == ContentType.TEXT

    def test_empty_page_filtered(self):
        pages = [(1, "   \n\n  "), (2, "Real content here.")]
        cleaned = clean_document(pages)
        assert len(cleaned) == 1
        assert cleaned[0].text == "Real content here."

    def test_unicode_normalisation(self):
        # NFKC normalises ligatures (ﬁ → fi) and compatibility forms.
        # Smart quotes (U+2019) are kept as-is by NFKC — that's correct behaviour.
        # What we care about is that the pipeline doesn't crash and produces clean text.
        raw = "Héllo\ufb01le caf\u00e9"   # ﬁ ligature → "fi"
        cp  = clean_page(raw)
        assert "fi" in cp.text    # ligature decomposed
        assert cp.text.strip()    # non-empty


# ═══════════════════════════════════════════════════════════════════════════
# CHUNKER TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestChunker:

    def _make_pages(self, text: str, ctype=ContentType.TEXT):
        from ingestion.cleaner import CleanedPage
        return [CleanedPage(text=text, page_number=1, content_type=ctype)]

    def test_basic_chunking_produces_chunks(self):
        long_text = " ".join([f"Sentence number {i} about Kubernetes." for i in range(200)])
        pages  = self._make_pages(long_text)
        chunks = chunk_pages(pages, source_file="test.txt", source_type=SourceType.TXT)
        assert len(chunks) > 1

    def test_short_text_is_single_chunk(self):
        text   = "Short document about Redis connection pooling."
        pages  = self._make_pages(text)
        chunks = chunk_pages(pages, source_file="test.txt", source_type=SourceType.TXT)
        assert len(chunks) == 1

    def test_table_not_split(self):
        table_text = "\n".join([
            "| Header A | Header B | Header C |",
            "|----------|----------|----------|",
        ] + [f"| Row {i} | Data {i} | Val {i} |" for i in range(50)])
        pages  = self._make_pages(table_text, ctype=ContentType.TABLE)
        chunks = chunk_pages(pages, source_file="test.txt", source_type=SourceType.TXT,
                             chunk_size=50)  # small size to force split if not protected
        # Tables must remain unsplit
        assert len(chunks) == 1
        assert chunks[0].content_type == ContentType.TABLE

    def test_chunk_ids_are_deterministic(self):
        text   = "Idempotency test. Same text always same ID."
        pages  = self._make_pages(text)
        run1   = chunk_pages(pages, source_file="file.txt", source_type=SourceType.TXT)
        run2   = chunk_pages(pages, source_file="file.txt", source_type=SourceType.TXT)
        assert run1[0].chunk_id == run2[0].chunk_id

    def test_chunk_ids_are_unique_within_doc(self):
        long_text = " ".join([f"Sentence {i} discusses microservices architecture." for i in range(300)])
        pages  = self._make_pages(long_text)
        chunks = chunk_pages(pages, source_file="file.txt", source_type=SourceType.TXT)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_total_chunks_is_consistent(self):
        long_text = " ".join([f"Word {i}" for i in range(500)])
        pages  = self._make_pages(long_text)
        chunks = chunk_pages(pages, source_file="file.txt", source_type=SourceType.TXT)
        expected_total = len(chunks)
        for c in chunks:
            assert c.total_chunks == expected_total

    def test_metadata_propagation(self):
        text   = "Test document for metadata."
        pages  = self._make_pages(text)
        chunks = chunk_pages(
            pages, source_file="file.txt", source_type=SourceType.TXT,
            extra_meta={"project": "Phoenix", "env": "prod"}
        )
        for c in chunks:
            assert c.metadata["project"] == "Phoenix"
            assert c.metadata["env"]     == "prod"

    def test_chunk_document_serialisation(self):
        text   = "Serialisation test for JSON output."
        pages  = self._make_pages(text)
        chunks = chunk_pages(pages, source_file="file.txt", source_type=SourceType.TXT)
        d = chunks[0].to_dict()
        # Must be JSON-serialisable
        json_str = json.dumps(d)
        loaded   = json.loads(json_str)
        assert loaded["text"] == text
        assert "chunk_id"      in loaded
        assert "source_file"   in loaded
        assert "token_estimate" in loaded

    def test_token_estimate_reasonable(self):
        text   = "A" * 400   # ~100 tokens
        pages  = self._make_pages(text)
        chunks = chunk_pages(pages, source_file="file.txt", source_type=SourceType.TXT)
        assert 80 <= chunks[0].token_estimate <= 120


# ═══════════════════════════════════════════════════════════════════════════
# PARSER TESTS  (text & JSON only – no PDF needed for CI)
# ═══════════════════════════════════════════════════════════════════════════

class TestParser:

    def test_parse_text_file(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("Hello world. This is a test document.", encoding="utf-8")
        pages = parse_file(f)
        assert len(pages) == 1
        assert "Hello world" in pages[0][1]

    def test_parse_markdown_file(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome content here.", encoding="utf-8")
        pages = parse_file(f)
        assert "Title" in pages[0][1]

    def test_parse_ticket_json_single(self, tmp_path):
        ticket = {
            "id": "T-001",
            "title": "Test ticket",
            "description": "Desc here.",
            "resolution": "Fixed.",
            "tags": ["k8s"]
        }
        f = tmp_path / "ticket.json"
        f.write_text(json.dumps(ticket), encoding="utf-8")
        pages = parse_file(f)
        assert len(pages) == 1
        assert "T-001" in pages[0][1]
        assert "Fixed." in pages[0][1]

    def test_parse_ticket_json_list(self, tmp_path):
        tickets = [
            {"id": "T-001", "title": "A", "description": "B", "resolution": "C", "tags": []},
            {"id": "T-002", "title": "D", "description": "E", "resolution": "F", "tags": []},
        ]
        f = tmp_path / "tickets.json"
        f.write_text(json.dumps(tickets), encoding="utf-8")
        pages = parse_file(f)
        assert len(pages) == 2

    def test_unsupported_extension_raises(self, tmp_path):
        f = tmp_path / "file.xlsx"
        f.write_bytes(b"dummy")
        with pytest.raises(ValueError, match="Unsupported file type"):
            parse_file(f)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_file(tmp_path / "nonexistent.pdf")


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestPipeline:

    def _build_sample_dir(self, tmp_path: Path) -> Path:
        data_dir = tmp_path / "raw"
        data_dir.mkdir()

        # Text doc
        (data_dir / "runbook.txt").write_text(
            " ".join([f"Sentence {i} about platform reliability engineering." for i in range(200)]),
            encoding="utf-8",
        )

        # Markdown with a table
        (data_dir / "config.md").write_text(
            "# Config\n\n| Key | Value |\n|-----|-------|\n| timeout | 30s |\n| retries | 3 |\n\n"
            "Some description about the configuration values shown above.",
            encoding="utf-8",
        )

        # JSON tickets
        tickets = [
            {
                "id": "T-99",
                "title": "Test ticket",
                "description": "CPU spike on node worker-3 after deploying v1.9.0.",
                "resolution": "Rolled back to v1.8.5. Root cause: N+1 query in new endpoint.",
                "tags": ["cpu", "performance", "rollback"],
            }
        ]
        (data_dir / "tickets.json").write_text(json.dumps(tickets), encoding="utf-8")

        return data_dir

    def test_returns_list_of_dicts(self, tmp_path):
        data_dir = self._build_sample_dir(tmp_path)
        result   = ingest_directory(data_dir, force_fallback=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)

    def test_all_required_fields_present(self, tmp_path):
        data_dir = self._build_sample_dir(tmp_path)
        result   = ingest_directory(data_dir, force_fallback=True)
        required = {
            "chunk_id", "text", "metadata", "source_file",
            "source_type", "content_type", "chunk_index",
            "total_chunks", "token_estimate", "ingested_at",
        }
        for chunk in result:
            missing = required - set(chunk.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_writes_jsonl_output(self, tmp_path):
        data_dir    = self._build_sample_dir(tmp_path)
        output_file = tmp_path / "out" / "chunks.jsonl"
        ingest_directory(data_dir, output_path=output_file, force_fallback=True)
        assert output_file.exists()
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) > 0
        # Every line must be valid JSON
        for line in lines:
            obj = json.loads(line)
            assert "chunk_id" in obj

    def test_writes_sidecar_report(self, tmp_path):
        data_dir    = self._build_sample_dir(tmp_path)
        output_file = tmp_path / "chunks.jsonl"
        ingest_directory(data_dir, output_path=output_file, force_fallback=True)
        report_file = output_file.with_suffix(".report.json")
        assert report_file.exists()
        report = json.loads(report_file.read_text())
        assert report["files_succeeded"] > 0
        assert report["total_chunks"]    > 0

    def test_missing_input_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ingest_directory(tmp_path / "nonexistent", force_fallback=True)

    def test_extra_metadata_in_every_chunk(self, tmp_path):
        data_dir = self._build_sample_dir(tmp_path)
        result   = ingest_directory(
            data_dir,
            extra_meta={"project": "RuntimeTerror", "version": "1.0"},
            force_fallback=True,
        )
        for chunk in result:
            assert chunk["metadata"]["project"] == "RuntimeTerror"
            assert chunk["metadata"]["version"] == "1.0"

    def test_source_type_detected_correctly(self, tmp_path):
        data_dir = self._build_sample_dir(tmp_path)
        result   = ingest_directory(data_dir, force_fallback=True)
        src_types = {c["source_type"] for c in result}
        # We have .txt, .md, .json files
        assert "txt"    in src_types
        assert "markdown" in src_types
        assert "ticket"   in src_types

    def test_chunk_ids_globally_unique(self, tmp_path):
        data_dir = self._build_sample_dir(tmp_path)
        result   = ingest_directory(data_dir, force_fallback=True)
        ids = [c["chunk_id"] for c in result]
        assert len(ids) == len(set(ids)), "All chunk IDs must be globally unique"

    def test_no_empty_text_chunks(self, tmp_path):
        data_dir = self._build_sample_dir(tmp_path)
        result   = ingest_directory(data_dir, force_fallback=True)
        for chunk in result:
            assert chunk["text"].strip(), "No chunk should have empty text"

    def test_graceful_handling_of_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = ingest_directory(empty_dir, force_fallback=True)
        assert result == []
