"""Chunk embedding table - vectors with full compatibility metadata.

WHAT THIS FILE DOES
    Stores ONE embedding per chunk together with the provider, model
    identifier and dimension that produced it.

WHY IT EXISTS
    Vectors from different models live in incompatible spaces. The
    recorded metadata is how rag_service detects a provider/model
    change and re-embeds instead of silently mixing vectors.

RULES
    - vector is a JSON list of floats (works on SQLite and PostgreSQL)
    - (provider, model, dimension) must match the query embedding
      before any similarity is computed
    - unchanged chunks keep their existing row (never re-embedded)

HOW IT CONNECTS
    rag_service.sync_document_embeddings() -> writes/updates rows
    rag_service.build_retrieval_context()  -> reads compatible rows
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), unique=True, index=True
    )

    # --- Compatibility metadata (never omitted) ------------------------
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    dimension: Mapped[int] = mapped_column(Integer)

    vector: Mapped[list[float]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.now()
    )

    chunk = relationship("DocumentChunk", back_populates="embedding")

    def __repr__(self) -> str:
        return (
            f"<ChunkEmbedding chunk={self.chunk_id} provider={self.provider} "
            f"model={self.model} dim={self.dimension}>"
        )
