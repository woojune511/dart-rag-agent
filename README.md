# AI Research & Reproduction Agent

A portfolio project answering to precise job descriptions by focusing on **MLOps, RAG, and Large Codebase Analysis**. This agent fetches AI research papers, parses them into a hybrid search RAG pipeline, tracks prompt performance via MLflow, and automatically analyzes associated GitHub codebases for module extraction.

## Tech Stack
- **Languages**: Python (FastAPI Engine)
- **AI/Orchestration**: LangGraph, LangChain, OpenAI/Anthropic SDK
- **Search/RAG**: Vector DB (Chroma/Qdrant), Elasticsearch
- **MLOps**: MLflow
- **Environment**: `uv` for venv management, Docker for deployment

## Project Structure
- `src/ingestion`: Logic for fetching papers and cloning code.
- `src/processing`: Parsers for PDFs and AST generation for Python.
- `src/storage`: Connectors to VectorDB and Elasticsearch.
- `src/agent`: LangGraph state machine routers and nodes.
- `src/ops`: MLflow hooks and evaluation pipelines.
- `src/api`: FastAPI entry points.

## How to run locally
Ensure you are using `uv` to manage the virtual environment.

```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```
