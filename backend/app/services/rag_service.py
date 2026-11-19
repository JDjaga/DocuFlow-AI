"""RAG service layer: chunking, embedding sync, retrieval, grounded answers.

WHAT THIS FILE DOES
    1. chunk_text()                  - split extracted text into citable chunks
    2. sync_document_embeddings()    - store embeddings for a document;
       unchanged chunks are NEVER re-embedded (content hash reuse) and a
       provider/model change is detected and triggers a clean re-embed
    3. retrieve_for_document()       - embed the question and retrieve the
       top chunks of ONE document, with user + document access control
    4. answer_from_context()         - run the grounded prompt through the
       SAME centralized provider manager as every other AI operation

RULES
    - Retrieval is scoped by document_id AND user_id: another user's
      chunks can never be returned.
    - Sources contain only chunks actually retrieved - citations are
      never invented.
    - Document content is framed as untrusted data (prompts.py) so a
      prompt injection inside a document cannot override instructions.
    - Embedding failures never break document analysis: chat simply
      falls back to full-document context.
    - Question embeddings are generated once per question - stored
      document embeddings are reused on every ask.

HOW IT CONNECTS
    document_service.analyze_and_save() -> sync_document_embeddings()
    chat_service.answer_question()      -> retrieve_for_document()
                                         -> answer_from_context()
    provider_manager.execute()          -> the generation provider
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk_embedding import ChunkEmbedding
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.services.ai.embedding_service import (
    cosine_similarity,
    get_embedding_service,
)
from app.services.ai.provider_manager import (
    ExecutionOutcome,
    get_provider_manager,
)

logger = logging.getLogger("docuflow.ai")

CHUNK_SIZE = 1200        # characters per chunk
CHUNK_OVERLAP = 200      # characters of context carried forward
MIN_CHUNKS_FOR_RAG = 4   # short docs answer better from the full text
TOP_K = 4                # chunks retrieved per question
MIN_SCORE = 0.05         # below this the excerpt is not relevant enough
EXCERPT_MAX = 600        # characters of each chunk placed in the prompt
SOURCE_EXCERPT_MAX = 240 # characters returned to the UI as a citation


# ----------------------------------------------------------------------
# Chunking
# ----------------------------------------------------------------------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph borders.

    Deterministic: the same text always produces the same chunks, which
    is what makes content-hash reuse of embeddings possible.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]

    overlap = max(0, min(overlap, size - 1))
    paragraphs = [part.strip() for part in cleaned.split("\n") if part.strip()]

    chunks: list[str] = []
    current = ""

    def _flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        # Hard-split single paragraphs longer than one chunk.
        while len(paragraph) > size:
            if current:
                _flush()
            chunks.append(paragraph[:size])
            paragraph = paragraph[size - overlap :]

        if not current:
            current = paragraph
        elif len(current) + 1 + len(paragraph) <= size:
            current = f"{current}\n{paragraph}"
        else:
            _flush()
            current = paragraph

    _flush()

    # Enforce overlap between hard-split neighbours.
    if overlap and len(chunks) > 1:
        overlapped: list[str] = []
        for index, chunk in enumerate(chunks):
            if index > 0 and not chunks[index - 1].endswith(chunk[:overlap]):
                tail = chunks[index - 1][-overlap:]
                chunk = f"{tail}{chunk}" if not chunk.startswith(tail) else chunk
            overlapped.append(chunk[: size + overlap])
        chunks = overlapped

    return chunks


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Embedding synchronisation
# ----------------------------------------------------------------------
def sync_document_embeddings(db: Session, document: Document) -> dict:
    """Create / reuse / refresh the embeddings of one document.

    Never raises: analysis must not fail because embeddings did. Returns
    a stats dict: {status, chunks, embedded, reused, removed, detail}.
    """
    stats = {
        "status": "ok",
        "chunks": 0,
        "embedded": 0,
        "reused": 0,
        "removed": 0,
        "detail": "",
    }

    try:
        service = get_embedding_service()
    except Exception as exc:  # noqa: BLE001 - config problems are not fatal
        stats.update(status="error", detail=f"Embedding backend unavailable: {exc}")
        logger.warning("Embeddings for document %s skipped: %s", document.id, exc)
        return stats

    existing = list(
        db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )
        .unique()
        .scalars()
        .all()
    )

    pieces = chunk_text((document.extracted_text or "").strip())
    stats["chunks"] = len(pieces)

    if not pieces:
        for chunk in existing:
            db.delete(chunk)
        db.commit()
        stats["detail"] = "Document has no text - embeddings removed."
        return stats

    signature = service.signature
    by_hash = {chunk.content_hash: chunk for chunk in existing}

    reused_rows: list[DocumentChunk] = []
    pending: list[tuple[int, str, str, DocumentChunk | None]] = []
    seen: set[str] = set()

    for index, content in enumerate(pieces):
        digest = _hash_content(content)
        if digest in seen:
            continue  # identical chunk inside one document
        seen.add(digest)

        row = by_hash.get(digest)
        embedding = row.embedding if row is not None else None
        compatible = (
            embedding is not None
            and (embedding.provider, embedding.model) == signature
        )
        if compatible:
            # Unchanged content + same embedding model -> reuse, never re-embed.
            if row.chunk_index != index:
                row.chunk_index = index
            reused_rows.append(row)
        else:
            pending.append((index, content, digest, row))

    embedded = 0
    if pending:
        try:
            results = service.embed_documents([content for _, content, _, _ in pending])
        except Exception as exc:  # noqa: BLE001 - sync must NEVER raise
            results = None
            stats.update(status="error", detail=str(exc))
            logger.warning("Embedding document %s failed: %s", document.id, exc)

        if results is not None:
            for (index, content, digest, row), result in zip(pending, results):
                if row is None:
                    row = DocumentChunk(
                        document_id=document.id,
                        user_id=document.user_id,
                        chunk_index=index,
                        content=content,
                        content_hash=digest,
                    )
                    db.add(row)
                    db.flush()  # assign the chunk id before the FK
                else:
                    row.chunk_index = index
                    row.content = content

                if row.embedding is not None:
                    # Provider/model changed -> replace the stale vector.
                    row.embedding.provider = result.provider
                    row.embedding.model = result.model
                    row.embedding.dimension = result.dimension
                    row.embedding.vector = result.vector
                else:
                    db.add(
                        ChunkEmbedding(
                            chunk_id=row.id,
                            provider=result.provider,
                            model=result.model,
                            dimension=result.dimension,
                            vector=result.vector,
                        )
                    )
                embedded += 1

    # Remove chunks that disappeared from the (re-analyzed) text.
    keep_ids = {row.id for row in reused_rows}
    keep_ids.update(
        row.id for _, _, _, row in pending if row is not None and row.id is not None
    )
    # Rows created in this transaction are not "stale" either.
    fresh_ids = {id(row) for _, _, _, row in pending if row is not None}
    removed = 0
    for chunk in existing:
        if chunk.id in keep_ids or id(chunk) in fresh_ids:
            continue
        db.delete(chunk)
        removed += 1

    stats.update(embedded=embedded, reused=len(reused_rows), removed=removed)
    if stats["status"] == "ok":
        stats["detail"] = (
            f"{len(pieces)} chunk(s): {embedded} embedded, "
            f"{len(reused_rows)} reused, {removed} removed."
        )

    db.commit()
    return stats


# ----------------------------------------------------------------------
# Retrieval
# ----------------------------------------------------------------------
@dataclass
class RetrievalContext:
    """Retrieved excerpts plus their honest source citations."""

    excerpts: str
    sources: list[dict] = field(default_factory=list)


def _load_compatible_rows(
    db: Session, document: Document, signature: tuple[str, str]
) -> list[tuple[DocumentChunk, ChunkEmbedding]]:
    rows = db.execute(
        select(DocumentChunk, ChunkEmbedding)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.user_id == document.user_id,
            ChunkEmbedding.provider == signature[0],
            ChunkEmbedding.model == signature[1],
        )
        .order_by(DocumentChunk.chunk_index)
    ).all()
    return [(row[0], row[1]) for row in rows]


def retrieve_for_document(
    db: Session, user: User, document: Document, question: str
) -> RetrievalContext | None:
    """Retrieve the top chunks of ONE owned document for `question`.

    Returns None when RAG does not apply (short document, embeddings
    unavailable/stale beyond repair, no relevant chunk) - the caller
    then uses full-document context, which preserves existing behaviour.

    Access control: document must already be ownership-verified by the
    caller AND every query filters on user_id as a second layer.
    """
    if document.user_id != user.id:  # defence in depth
        return None

    total_chunks = db.execute(
        select(DocumentChunk.id).where(DocumentChunk.document_id == document.id)
    ).all()
    if len(total_chunks) < MIN_CHUNKS_FOR_RAG:
        return None  # short document: full text answers better

    try:
        service = get_embedding_service()
        rows = _load_compatible_rows(db, document, service.signature)
        if not rows:
            # Embedding provider/model changed (or first run): rebuild once.
            sync_document_embeddings(db, document)
            rows = _load_compatible_rows(db, document, service.signature)
        if not rows:
            return None

        query_vector = service.embed_query(question).vector
    except Exception as exc:  # noqa: BLE001 - RAG must never break chat
        logger.warning(
            "RAG retrieval for document %s degraded to full text: %s",
            document.id,
            exc,
        )
        return None

    scored: list[tuple[float, DocumentChunk]] = []
    for chunk, embedding in rows:
        vector = embedding.vector
        if isinstance(vector, str):  # defensive: JSON columns may come back raw
            try:
                vector = json.loads(vector)
            except ValueError:
                continue
        if not isinstance(vector, list) or len(vector) != len(query_vector):
            continue  # never compare incompatible vectors
        score = cosine_similarity(query_vector, [float(value) for value in vector])
        if score >= MIN_SCORE:
            scored.append((score, chunk))

    if not scored:
        return None  # nothing relevant -> honest full-text answer instead

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:TOP_K]

    excerpts = "\n\n".join(
        f"[chunk {chunk.chunk_index}] {chunk.content[:EXCERPT_MAX]}"
        for _, chunk in top
    )
    sources = [
        {
            "chunk_index": chunk.chunk_index,
            "excerpt": chunk.content[:SOURCE_EXCERPT_MAX],
            "score": round(score, 3),
        }
        for score, chunk in top
    ]
    return RetrievalContext(excerpts=excerpts, sources=sources)


# ----------------------------------------------------------------------
# Grounded generation (through the centralized manager)
# ----------------------------------------------------------------------
def answer_from_context(context: RetrievalContext, question: str) -> ExecutionOutcome:
    """Answer from retrieved excerpts via the provider manager.

    The SAME operation ("answer_question") runs on whichever provider
    the manager selects, so RAG inherits retry/fallback automatically.
    """
    manager = get_provider_manager()
    return manager.execute(
        "answer_question",
        lambda provider: provider.answer_with_excerpts(context.excerpts, question),
    )
