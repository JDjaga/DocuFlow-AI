"""Task table.

WHAT THIS FILE DOES
    Stores workflow tasks. A task can be created manually by the user
    (document_id = NULL) or generated from a document's AI action items
    (document_id = the owning document).

WHY IT EXISTS
    It is the "turn documents into decisions" half of the product:
    analysis results become tracked, status-driven work.

HOW IT CONNECTS
    task_service.py      -> CRUD with ownership checks
    document_service.py  -> converts action_items into Task rows
    routers/tasks.py     -> REST endpoints
    routers/dashboard.py -> counts pending vs completed
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PRIORITIES, TASK_STATUSES
from app.database.base import Base, utcnow


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Ownership: users can only ever see their own tasks.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Nullable: manually created tasks are not linked to a document.
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="Medium", index=True)
    status: Mapped[str] = mapped_column(String(15), default=TASK_STATUSES[0], index=True)

    # Display name of whoever the task is assigned to (simple, no extra table).
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Only set when a due date was explicitly identifiable in the document.
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Extra data kept for reference (for example the source action item).
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    # Relationships
    owner = relationship("User", back_populates="tasks")
    document = relationship("Document", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"
