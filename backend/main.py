from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, chat, health, study_logs, research_exports
from app.config import get_settings
from app.core.container import build_application_container
from app.database import init_db
from app.core.errors import ApplicationError
import logging

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        app.state.container = build_application_container(settings)
        app.state.container_error = None
    except Exception as exc:
        # The API remains available for readiness diagnosis, but participant
        # activation must fail while the container is invalid.
        app.state.container = None
        app.state.container_error = exc
        logger.error("Application container is not ready: %s", type(exc).__name__)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Source-aware university policy assistant backend prototype.",
    lifespan=lifespan,
)


@app.exception_handler(ApplicationError)
async def application_error_handler(_, error: ApplicationError):
    return JSONResponse(
        status_code=error.definition.http_status,
        content={"detail": error.safe_payload()},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(study_logs.router, prefix="/api/study", tags=["study"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(research_exports.router, prefix="/api/admin", tags=["admin"])
