"""Model registry.

Importing this package registers every table on `Base.metadata`, which is
required before `Base.metadata.create_all()` or `alembic revision
--autogenerate` can see the schema.
"""
from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.task import Task
from app.models.user import User

__all__ = ["User", "Document", "Task", "DocumentChunk", "ChunkEmbedding"]
