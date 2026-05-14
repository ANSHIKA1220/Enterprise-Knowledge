# Vector Database & Semantic Search Module

## Overview

This module serves as the **fast-retrieval memory** system for the Enterprise Knowledge Copilot. It transforms standardized chunked JSON objects from the Data Ingestion Pipeline into mathematically dense vector embeddings, running entirely **locally** to prevent cloud API rate limits and ensure scalability.

The Vector Database provides immediate semantic context to:
- **LangChain / LangGraph** agent workflows (Arpan's module)
- **The Confidence & Routing Engine** (Mohit's module)

---

## ✨ Key Features

- ⚡ **Fast Local Embeddings** — HuggingFace `all-MiniLM-L6-v2` model runs entirely on-device
- 🗄️ **Serverless Vector Storage** — ChromaDB with SQLite persistence, no external databases
- 🔄 **Singleton Pattern** — Prevents memory leaks and duplicate ML model loading
- 📦 **Safe Batch Ingestion** — Built-in safeguards to prevent out-of-memory crashes
- ⚙️ **Async-First Design** — Optimized for high-speed FastAPI backends
- 🤖 **LangChain Integration** — Pre-built `@tool` wrapper for instant agent integration
- 🎯 **Strict Metadata Tracking** — Accurate source and page-number citation

---

## 📁 Project Structure

```
vector_search/
├── __init__.py
├── .env.example
├── agent_tool.py
├── requirements.txt
├── run_ingestion.py
├── vector_engine.py
└── README.md
```

---

## 🚀 Quick Start

### 1. Create a Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r vector_search/requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory. You can copy from `.env.example`:

```env
CHROMA_PERSIST_DIR="./chroma_db"
CHROMA_COLLECTION="enterprise_kb"
USE_LOCAL_EMBEDDINGS="True"
```

### 4. Verify Installation

```bash
python -c "from vector_search.vector_engine import ChromaSearchEngine; print('Import successful')"
```

**Expected Output:**
```
Import successful
```

---

## 📚 Running the Ingestion Pipeline

To populate the Vector Database, execute the ingestion script from the **repository root** directory:

```bash
python vector_search/run_ingestion.py
```

**Expected Output:**
```
INFO: Initializing Local ChromaSearchEngine...
INFO: Local Vector store initialized successfully.
INFO: Starting ingestion from directory...
INFO: Vector data ingestion completed successfully.
INFO: Vector Database successfully populated!
```

### Generated Output

After running the build script, a new directory is created in your repository root:

```
chroma_db/               # SQLite database with embedded vectors
```

---

## 💻 Python API Usage

### Basic Retrieval

Test the retrieval mechanism without the LangGraph agent:

```python
import asyncio
from vector_search.vector_engine import ChromaSearchEngine

async def test_search():
    engine = ChromaSearchEngine()
    result = await engine.aretrieve_context("How do I fix a 504 Gateway Error?")
    print(result)

asyncio.run(test_search())
```

---

## 🔗 Integration with LangGraph

This module is pre-configured as a tool for the Multi-Agent Orchestrator.

Arpan's LangGraph workflow can consume it directly:

```python
from vector_search.agent_tool import semantic_search_tool

# Add to your LangGraph node's tools list
agent_tools = [semantic_search_tool]
```

---

## 🚫 Git Ignore Configuration

Add the following to your `.gitignore` to prevent tracking heavy files:

```
venv/
.venv/
__pycache__/
*.pyc
chroma_db/
.env
```

---

## 🔧 Troubleshooting

### `ModuleNotFoundError: No module named 'vector_search'`

**Solution:** Ensure you're running commands from the **repository root**, not from inside the `vector_search/` folder.

```bash
# ✅ Correct
python vector_search/run_ingestion.py

# ❌ Wrong
cd vector_search && python run_ingestion.py
```

### `Killed` or `MemoryError` During Ingestion

The HuggingFace embedding model requires ~1GB of RAM.

**Solutions:**
- Close other applications to free memory
- Reduce `batch_size` in `vector_engine.py`
- Increase available system memory

---

## 🎯 Main Entry Points

### Database Builder
```python
from vector_search.run_ingestion import run_end_to_end_ingestion
```

### Agent Tool (For LangGraph)
```python
from vector_search.agent_tool import semantic_search_tool
```

---

