"""Dashboard statistics and analytics.

WHAT THIS FILE DOES
    get_stats()     -> the four KPI numbers shown on the dashboard
    get_analytics() -> data shaped for Recharts (activity, status, priority)

WHY IT EXISTS
    All numbers on the dashboard come from real SQL aggregation. Nothing
    is invented in the frontend.

HOW IT CONNECTS
    routers/dashboard.py calls these with the authenticated user and
    returns the result as JSON to React.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import PRIORITIES, TASK_STATUSES
from app.database.base import utcnow
from app.models.document import Document
from app.models.task import Task
from app.models.user import User

ACTIVITY_DAYS = 14


def get_stats(db: Session, user: User) -> dict:
    """Four KPI values, computed from the user's own rows only."""
    documents = db.execute(
        select(Document.processing_status).where(Document.user_id == user.id)
    ).scalars().all()

    statuses = db.execute(
        select(Task.status).where(Task.user_id == user.id)
    ).scalars().all()

    total_documents = len(documents)
    analyzed_documents = sum(1 for status in documents if status == "completed")
    failed_documents = sum(1 for status in documents if status == "failed")

    pending = sum(1 for status in statuses if status == "pending")
    in_review = sum(1 for status in statuses if status == "in_review")
    completed = sum(1 for status in statuses if status == "completed")

    high_priority_documents = db.execute(
        select(Document).where(Document.user_id == user.id, Document.priority == "High")
    ).unique().scalars().all()

    due_soon = [
        task
        for task in db.execute(select(Task).where(Task.user_id == user.id)).scalars().all()
        if task.due_date is not None
        and task.status != "completed"
        and task.due_date <= (utcnow().date() + timedelta(days=7))
    ]

    completion_rate = round((completed / len(statuses)) * 100, 1) if statuses else 0.0

    return {        "total_documents": total_documents,
        "documents_analyzed": analyzed_documents,
        "documents_failed": failed_documents,
        "pending_tasks": pending,
        "completed_tasks": completed,
        "in_review_tasks": in_review,
        "total_tasks": len(statuses),
        "high_priority_documents": len(high_priority_documents),
        "tasks_due_soon": len(due_soon),
        "task_completion_rate": completion_rate,
    }


def get_analytics(db: Session, user: User) -> dict:
    """Chart-ready data: activity over time, task status, document priority."""
    return {
        "activity": _activity_series(db, user),
        "task_status": _task_status_series(db, user),
        "document_priority": _document_priority_series(db, user),
    }


def _activity_series(db: Session, user: User) -> list[dict]:
    """Documents and tasks created per day for the last 14 days.

    Grouping is done in Python so the same code works on SQLite and
    PostgreSQL without database-specific date functions.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=ACTIVITY_DAYS - 1)).date()

    document_counts: Counter = Counter()
    for created_at in (
        db.execute(
            select(Document.created_at).where(
                Document.user_id == user.id, Document.created_at >= datetime(since.year, since.month, since.day)
            )
        )
        .scalars()
        .all()
    ):
        document_counts[created_at.date()] += 1

    task_counts: Counter = Counter()
    for created_at in (
        db.execute(
            select(Task.created_at).where(
                Task.user_id == user.id, Task.created_at >= datetime(since.year, since.month, since.day)
            )
        )
        .scalars()
        .all()
    ):
        task_counts[created_at.date()] += 1

    today = datetime.now(timezone.utc).date()
    series = []
    for offset in range(ACTIVITY_DAYS):
        day = since + timedelta(days=offset)
        if day > today:
            break
        series.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%b %d"),
                "documents": document_counts.get(day, 0),
                "tasks": task_counts.get(day, 0),
            }
        )
    return series


def _task_status_series(db: Session, user: User) -> list[dict]:
    rows = db.execute(select(Task.status).where(Task.user_id == user.id)).scalars().all()
    counter = Counter(rows)
    labels = {"pending": "Pending", "in_review": "In Review", "completed": "Completed"}
    return [
        {"name": labels[status], "value": counter.get(status, 0)}
        for status in TASK_STATUSES
    ]


def _document_priority_series(db: Session, user: User) -> list[dict]:
    rows = db.execute(select(Document.priority).where(Document.user_id == user.id)).scalars().all()
    counter: defaultdict = defaultdict(int)
    for priority in rows:
        counter[priority] += 1
    return [{"name": priority, "value": counter.get(priority, 0)} for priority in PRIORITIES]
