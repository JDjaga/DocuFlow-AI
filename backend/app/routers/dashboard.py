"""Dashboard endpoints (KPI numbers and chart data).

WHAT THIS FILE DOES
    GET /api/dashboard/stats     - the four KPI cards
    GET /api/dashboard/analytics - Recharts-ready activity/status/priority data

WHY IT EXISTS
    Every number on the dashboard must come from the database, never from
    static frontend data.

HOW IT CONNECTS
    frontend/services/dashboard.js -> these endpoints
    services/dashboard_service.py  -> SQL/Python aggregation
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import get_current_user
from app.models.user import User
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """KPI values for the current user only."""
    return dashboard_service.get_stats(db, user)


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Series used by the dashboard charts."""
    return dashboard_service.get_analytics(db, user)
