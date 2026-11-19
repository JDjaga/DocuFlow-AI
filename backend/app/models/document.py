"""Document table.

WHAT THIS FILE DOES
    Stores the uploaded file's text plus everything the AI extracted:
    summary, category, priority, key entities, action items, observations.

WHY IT EXISTS
    The document is the central entity of DocuFlow AI. Tasks are created
    from its action items, and the dashboard counts come from this table.

HOW IT CONNECTS
    file_service.py    -> writes extracted_text
    ai_service.py      -> fills summary / category / priority / entities
    document_service.py-> persists the row, applies filters and pagination
    routers/documents.py -> exposes it as JSON
"""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PROCESSING_STATUSES, PRIORITIES
from app.database.base import Base, utcnow


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Ownership: every query is filtered by this column.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="General Document", index=True)

    # "task"     -> work document: action items can become workflow tasks
    # "general"  -> reference document: analysis + chat only, no tasks
    document_type: Mapped[str] = mapped_column(
        String(10), default="task", server_default="task", index=True
    )

    extracted_text: Mapped[str] = mapped_column(Text, default="")

    # --- AI results ---------------------------------------------------
    summary: Mapped[str] = mapped_column(Text, default="")
    key_entities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    priority: Mapped[str] = mapped_column(String(10), default="Medium", index=True)
    priority_reason: Mapped[str] = mapped_column(Text, default="")
    observations: Mapped[list[str]] = mapped_column(JSON, default=list)
    action_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # pending -> completed / failed
    processing_status: Mapped[str] = mapped_column(
        String(15), default=PROCESSING_STATUSES[1], index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Free text written by the user after reviewing the analysis.
    user_notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    # User -> Documents is a one-to-many relationship (see models/user.py)
    owner = relationship("User", back_populates="documents")

    # Document -> Tasks (one document can spawn several action item tasks)
    tasks = relationship("Task", back_populates="document")

    # Document -> Chunks (RAG retrieval; deleted together with the document)
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r} priority={self.priority}>"
