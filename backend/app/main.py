"""DocuFlow AI - FastAPI application entry point.

WHAT THIS FILE DOES
    - builds the FastAPI app
    - adds CORS so the React dev server can call the API
    - registers the five routers (auth, documents, tasks, dashboard, health)
    - converts our own AppError into clean JSON error responses
    - creates the database tables on first start (Alembic can take over later)
    - prints a startup banner with the correct local URL (port 8001)

WHY IT EXISTS
    Everything that is "application wide" lives here; business logic lives
    in services and HTTP details live in routers.

HOW TO RUN
    cd backend
    uvicorn app.main:app --reload --port 8001
    Then open http://localhost:8001/docs for interactive API documentation.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 - imports every table so create_all sees them
from app.core.config import settings
from app.database.base import Base
from app.database.connection import engine
from app.routers import auth, chat, dashboard, documents, health, tasks
from app.services.ai.embedding_service import warm_up_in_background
from app.utils.errors import AppError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("docuflow")

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config, create tables on startup, shut down cleanly."""
    # Fail fast on malformed AI configuration; warn (not crash) on
    # incomplete-but-valid setups such as a missing provider key.
    try:
        config_warnings = settings.validate_ai_settings()
    except ValueError as exc:
        logger.error("Invalid AI configuration: %s", exc)
        raise RuntimeError(f"Invalid AI configuration: {exc}") from exc
    for warning in config_warnings:
        logger.warning("AI config: %s", warning)

    # create_all is safe: it only creates tables that do not exist yet.
    # Alembic manages the schema once migrations are in place (see documentation/03).
    Base.metadata.create_all(bind=engine)

    # Import PyTorch + load the local embedding model in the background so
    # the first analyze/chat request does not wait ~20s for it (no-op for
    # mock/gemini embedding backends).
    if settings.EMBEDDING_PROVIDER.strip().lower() in ("auto", "local"):
        warm_up_in_background()

    logger.info(
        "%s v%s ready | AI mode: %s | database: %s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ai_provider,
        settings.DATABASE_URL.split("://")[0],
    )
    yield
    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Enterprise document intelligence and workflow management platform. "
        "Turn documents into decisions."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# --- CORS ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,  # frontend origins from .env
    allow_credentials=True,  # cookies would be allowed; we use Bearer tokens
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Error handling -----------------------------------------------------
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Turn our typed application errors into {\"detail\": ...}."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with readable field messages instead of raw Pydantic output."""
    messages = []
    for error in exc.errors():
        field = " -> ".join(str(part) for part in error.get("loc", []) if part != "body")
        messages.append(f"{field}: {error.get('msg', 'invalid value')}" if field else error.get("msg", "invalid value"))
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last line of defence: never leak a stack trace to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred."})


# --- Routes -------------------------------------------------------------
@app.get("/", tags=["Health"], include_in_schema=False)
def root():
    return {
        "name": settings.APP_NAME,
        "tagline": "Turn Documents into Decisions.",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
        "local_url": "http://localhost:8001",
    }


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(dashboard.router)


@app.middleware("http")
async def add_process_time(request: Request, call_next):  # noqa: ANN001
    """Small request timer - useful while debugging slow endpoints."""
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - started) * 1000, 1))
    return response
