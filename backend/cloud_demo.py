"""Single-worker cloud entry point, never used by the local research server."""

import os
from pathlib import Path

from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.cloud_demo_guard import CloudDemoGuard
from main import app

settings = get_settings()
if (
    settings.app_env != "cloud_demo"
    or settings.study_mode != "development"
    or settings.execution_context != "development"
    or settings.embedding_provider != "openai"
    or settings.vector_store_provider != "chroma"
    or settings.vector_store_allow_fallback
    or not os.environ.get("UNI_NAVIGATOR_DB_PATH", "").startswith("/tmp/")
):
    raise RuntimeError("Cloud demo requires isolated development data and OpenAI/Chroma.")


@app.get("/healthz")
def healthz():
    container = getattr(app.state, "container", None)
    if container is None:
        return JSONResponse({"status": "unavailable"}, 503)
    status = container.chat_orchestrator.vector_store.status()
    ready = status.active_provider == "chroma" and not status.fallback_used and status.chunk_count > 0
    return JSONResponse({
        "status": "ready" if ready else "unavailable",
        "mode": "public_demo", "vectorProvider": status.active_provider,
        "fallbackUsed": status.fallback_used, "policyFiles": status.source_count,
        "evidencePassages": status.chunk_count,
    }, 200 if ready else 503)


app.add_middleware(CloudDemoGuard, chat_limit=int(os.getenv("CLOUD_DEMO_CHAT_LIMIT", "30")))
app.mount("/", StaticFiles(
    directory=Path(__file__).resolve().parents[1] / "frontend" / "out", html=True,
), name="demo_frontend")
