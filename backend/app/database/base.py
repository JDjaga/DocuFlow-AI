"""Declarative base shared by every SQLAlchemy model.

WHAT THIS FILE DOES
    - defines `Base`, the class all tables inherit from
    - provides `utcnow()`, the default timestamp used by created_at/updated_at

WHY IT EXISTS
    SQLAlchemy needs one common ancestor to discover the metadata of all
    tables (used by create_all and by Alembic autogenerate).

HOW IT CONNECTS
    models/user.py, models/document.py, models/task.py all do
    `from app.database.base import Base`.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def utcnow() -> datetime:
    """Current UTC time without timezone info.

    Naive UTC keeps SQLite and PostgreSQL behaving identically, which
    avoids the classic 'can't compare offset-naive and offset-aware
    datetimes' bug for beginners.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
