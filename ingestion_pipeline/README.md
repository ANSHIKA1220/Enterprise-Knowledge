# Data Ingestion & Processing Pipeline

## Overview

This module is the first stage of the Enterprise Knowledge Copilot pipeline.

It takes raw enterprise documents such as:

* PDFs
* Markdown files
* Text files
* Log files
* Support tickets (JSON)

and converts them into standardized chunked JSON objects that can be used directly by:

* ChromaDB (vector database)
* Neo4j (knowledge graph)
* LangChain / LangGraph workflows

---

## Features

* PDF parsing using LlamaParse
* Automatic fallback to PyMuPDF if LlamaParse is unavailable
* TXT / Markdown / LOG / JSON ticket parsing
* Unicode normalization and text cleaning
* Table and code block detection
* Sentence-aware overlapping chunking
* Deterministic SHA-256 chunk IDs
* JSONL output (`chunks.jsonl`)
* Summary report (`chunks.report.json`)
* 33 automated tests

---

## Project Structure

```text
ingestion_pipeline/
├── ingestion/
│   ├── __init__.py
│   ├── models.py
│   ├── parser.py
│   ├── cleaner.py
│   ├── chunker.py
│   └── pipeline.py
├── sample data/
│   ├── mock_tickets.json
│   ├── k8s_runbook.md
│   ├── notes.txt
│   ├── app.log
│   └── RuntimeTerror.pdf
├── tests/
│   └── test_pipeline.py
├── output/              # Generated automatically (ignored by git)
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

---

# Setup Instructions

## 1. Create a Virtual Environment

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Windows CMD

```cmd
python -m venv venv
venv\Scripts\activate
```

---

## 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Set LlamaParse API Key (Optional but Recommended)

Get your API key from:
https://cloud.llamaindex.ai

### PowerShell

```powershell
$env:LLAMA_CLOUD_API_KEY="your_api_key"
```

### CMD

```cmd
set LLAMA_CLOUD_API_KEY=your_api_key
```

If this variable is not set, the pipeline automatically falls back to PyMuPDF for PDFs.

---

## 4. Verify Installation

```bash
python -c "import ingestion; print('Import successful')"
```

Expected output:

```text
Import successful
```

---

# Running Tests

```bash
pytest tests/ -v
```

Expected output:

```text
33 passed
```

---

# Running the Pipeline

```bash
python -m ingestion.pipeline "sample data" --output output/chunks.jsonl
```

Expected output:

```text
Done – 16 chunk(s) written to output/chunks.jsonl
```

---

# Output Files

After running the pipeline, the following files are created:

```text
output/
├── chunks.jsonl
└── chunks.report.json
```

---

# Checking the Report

### Windows

```cmd
type output\chunks.report.json
```

Expected fields:

```json
{
  "files_attempted": 5,
  "files_succeeded": 5,
  "files_failed": 0,
  "total_chunks": 16,
  "errors": []
}
```

---

# Python API Usage

```python
from ingestion.pipeline import ingest_directory

chunks = ingest_directory(
    input_dir="sample data",
    output_path="output/chunks.jsonl"
)

print("Total chunks:", len(chunks))
print(chunks[0])
```

---

# Supported Input Formats

| Extension | Description      |
| --------- | ---------------- |
| `.pdf`    | PDF documents    |
| `.txt`    | Plain text files |
| `.md`     | Markdown files   |
| `.log`    | Log files        |
| `.json`   | Support tickets  |

---

# Output Schema

Each chunk contains:

* `chunk_id`
* `text`
* `metadata`
* `source_file`
* `source_type`
* `content_type`
* `chunk_index`
* `total_chunks`
* `page_number`
* `char_start`
* `char_end`
* `token_estimate`
* `ingested_at`

---

# Integration with ChromaDB

```python
from ingestion.pipeline import ingest_directory
import chromadb

chunks = ingest_directory("sample data")

client = chromadb.Client()
collection = client.get_or_create_collection("enterprise_kb")

collection.upsert(
    ids=[c["chunk_id"] for c in chunks],
    documents=[c["text"] for c in chunks],
    metadatas=[c["metadata"] for c in chunks],
)
```

---

# Integration with Neo4j

The graph module can consume the same `chunks.jsonl` file and extract entities and relationships.

---

# Sample Data Included

The repository includes sample files for testing:

* `mock_tickets.json`
* `k8s_runbook.md`
* `notes.txt`
* `app.log`
* `RuntimeTerror.pdf`

---

# Validation Summary

This module has been fully validated.

* 33/33 tests passed
* LlamaParse integration verified
* PyMuPDF fallback verified
* Successfully processed 5 files
* Generated 16 chunks
* Zero errors

---

# Git Ignore Recommendations

The following files are excluded from version control:

```gitignore
venv/
.venv/
__pycache__/
*.pyc
.pytest_cache/
output/
*.jsonl
*.report.json
.env
.vscode/
.idea/
```

---

# Troubleshooting

## `ModuleNotFoundError: No module named 'ingestion'`

Ensure `pytest.ini` contains:

```ini
[pytest]
pythonpath = .
```

## PowerShell Execution Policy Error

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## LlamaParse Not Working

Check:

```bash
echo %LLAMA_CLOUD_API_KEY%
```

---

# Main Entry Point

```python
from ingestion.pipeline import ingest_directory
```

Function signature:

```python
ingest_directory(
    input_dir,
    output_path=None,
    chunk_size=512,
    overlap=64,
    extra_meta=None,
    force_fallback=False,
)
```

---

# Status

This module is complete and ready for integration with the Enterprise Knowledge Copilot.
