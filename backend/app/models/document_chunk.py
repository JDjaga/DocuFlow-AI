"""Document chunk table - the unit of RAG retrieval.

WHAT THIS FILE DOES
    Stores overlapping text chunks produced from a document's
    extracted_text, together with a content hash used to detect
    unchanged chunks (they are never re-embedded).

WHY IT EXISTS
    Retrieval needs small, citable pieces of a document. The hash is
    what makes "reuse existing embeddings" possible when a document is
    re-analyzed or the embedding model changes.

HOW IT CONNECTS
    rag_service.chunk_text()          -> rows are written here
    rag_service.build_retrieval_context() -> reads chunks + embeddings
    Document (models/document.py)     -> one-to-many, deleted with it
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # Ownership is denormalised so retrieval can filter by user_id in
    # the same query as the document - a second access-control layer.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.now()
    )

    document = relationship("Document", back_populates="chunks")
    # One chunk -> at most one embedding (with provider/model metadata).
    embedding = relationship(
        "ChunkEmbedding",
        uselist=False,
        back_populates="chunk",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} document={self.document_id} index={self.chunk_index}>"
