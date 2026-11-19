"""Health endpoints.

WHAT THIS FILE DOES
    GET /api/health     - is the API up and can it reach the database?
    GET /api/health/ai  - which AI mode is active and is it configured?

WHY IT EXISTS
    The API Health page in the frontend shows live component status, and
    Docker/GitHub Actions can poll these routes as a readiness check.

RULE
    Never expose API keys, database passwords or raw connection strings.
    Only booleans and safe labels are returned.
"""
import time

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.connection import get_db
from app.services import ai_service

router = APIRouter(prefix="/api", tags=["Health"])

START_TIME = time.time()


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    """Overall service health with a real database round-trip."""
    database_status = "healthy"
    database_detail = "Database connection is working."
    http_status = 200

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any driver error means "not healthy"
        database_status = "unavailable"
        database_detail = "Database connection failed."
        http_status = 503
        response.status_code = 503
        _ = exc  # the exception itself is intentionally not returned to the client

    overall = "healthy" if http_status == 200 else "unavailable"

    return {
        "status": overall,
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "database": {"status": database_status, "detail": database_detail},
        "environment": "development" if settings.MOCK_AI else "production-like",
        "endpoints": {
            "documents": "/api/documents",
            "tasks": "/api/tasks",
            "dashboard": "/api/dashboard",
            "docs": "/docs",
        },
    }


@router.get("/health/ai")
def ai_health():
    """AI provider status - Mock or Gemini - without leaking any secret."""
    return ai_service.health_check()
