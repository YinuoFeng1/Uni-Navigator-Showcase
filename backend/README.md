# Uni-Navigator Backend

FastAPI backend with a shared live RAG orchestrator, OpenAI generation and
embeddings, Chroma retrieval, citation validation, SQLite research logging and
administrative exports. Test doubles are limited to automated tests; application
chat does not silently return mock or fixed answers on failure.

Follow [repository setup](../README.md) to obtain policies, configure a private
API key and build a local vector store. From this directory:

```bash
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
.venv/bin/pytest
```

Local API docs: `http://127.0.0.1:8000/docs`.
Health check: `http://127.0.0.1:8000/api/health`.
Keep administrative APIs private; the backend is not a hardened public service.
