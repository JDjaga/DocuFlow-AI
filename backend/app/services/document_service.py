"""Document business logic: analysis flow, filtering, CRUD.

WHAT THIS FILE DOES
    analyze_and_save()      - text -> AI -> validated rows in the database
    reanalyze_document()    - run the AI again on an existing document
    list_documents()        - server-side search + filters + sort + pagination
    get/update/delete       - always scoped to the logged-in user

WHY IT EXISTS
    Routers stay declarative; every rule that touches data lives here and
    can be unit tested without HTTP.

HOW IT CONNECTS
    routers/documents.py -> these functions
    ai_service.py        -> produce the analysis
    task_service.py      -> used when action items become tasks

INTERVIEW NOTE
    "Every query includes user_id. That single line is what stops one user
     from reading another user's document by guessing its id - they get a
     404, so the resource's existence is not even revealed."
"""
import logging
import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import DOCUMENT_CATEGORIES, DOCUMENT_TYPES, PRIORITIES, PROCESSING_STATUSES
from app.models.document import Document
from app.models.task import Task
from app.models.user import User
from app.schemas.ai import AIAnalysis
from app.schemas.document import DocumentDetail, DocumentListItem, DocumentUpdate
from app.services import ai_service, rag_service
from app.utils.errors import bad_request, not_found

logger = logging.getLogger("docuflow.ai")

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def document_to_detail(db: Session, document: Document) -> DocumentDetail:
    """Convert a Document row into the full API representation."""
    task_count = db.execute(
        select(func.count(Task.id)).where(Task.document_id == document.id)
    ).scalar_one()
    detail = DocumentDetail.model_validate(document)
    detail.task_count = task_count
    return detail


def document_to_item(document: Document) -> DocumentListItem:
    """Convert a Document row into the compact table representation."""
    return DocumentListItem.model_validate(document)


# --- Analysis ----------------------------------------------------------
def analyze_and_save(
    db: Session,
    user: User,
    *,
    text: str,
    original_filename: str | None = None,
    title: str = "",
    document_type: str = "task",
) -> tuple[Document, str, str | None]:
    """Run the AI over `text` and persist a brand new document.

    Returns:
        (document, provider_label, fallback_notice) - the label tells
        the UI which provider actually answered (mock/gemini/openrouter/
        ollama); the notice is set only when automatic fallback happened.
    """
    clean_text = ai_service.ensure_text_length(text)
    analysis, provider, notice = ai_service.analyze_text(clean_text)

    document = Document(
        user_id=user.id,
        original_filename=original_filename,
        title=_pick_title(title, original_filename, clean_text, analysis),
        category=analysis.category,
        document_type=document_type if document_type in DOCUMENT_TYPES else "task",
        extracted_text=clean_text,
        summary=analysis.summary,
        key_entities=[entity.model_dump() for entity in analysis.key_entities],
        priority=analysis.priority,
        priority_reason=analysis.priority_reason,
        observations=analysis.observations,
        action_items=(
            []
            if document_type not in DOCUMENT_TYPES or document_type == "general"
            else [item.model_dump(mode="json") for item in analysis.action_items]
        ),
        processing_status=PROCESSING_STATUSES[1],  # completed
        user_notes=f"Analyzed with {provider} AI mode.",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # RAG embeddings are best-effort: a failure never breaks analysis.
    _sync_embeddings_safely(db, document)
    return document, provider, notice


def reanalyze_document(
    db: Session, user: User, document: Document, text: str | None = None
) -> tuple[Document, str, str | None]:
    """Re-run the AI on an existing document (update in place, no duplicate row)."""
    clean_text = ai_service.ensure_text_length(text or document.extracted_text)
    analysis, provider, notice = ai_service.analyze_text(clean_text)

    _apply_analysis(document, analysis, clean_text)
    document.user_notes = f"Re-analyzed with {provider} AI mode."
    db.commit()
    db.refresh(document)

    _sync_embeddings_safely(db, document)
    return document, provider, notice


def _sync_embeddings_safely(db: Session, document: Document) -> None:
    """Embed chunks for RAG without ever failing the analysis request.

    Unchanged chunks are reused (content hash), so re-analyzing the same
    text never re-embeds anything.
    """
    try:
        stats = rag_service.sync_document_embeddings(db, document)
        if stats.get("status") == "error":
            logger.warning(
                "Embeddings for document %s: %s", document.id, stats.get("detail")
            )
    except Exception:  # noqa: BLE001 - embeddings are optional by design
        logger.warning(
            "Embedding sync failed for document %s", document.id, exc_info=True
        )


def _apply_analysis(document: Document, analysis: AIAnalysis, text: str) -> None:
    """Write AI results onto an existing document row."""
    document.extracted_text = text
    document.category = analysis.category
    document.summary = analysis.summary
    document.key_entities = [entity.model_dump() for entity in analysis.key_entities]
    document.priority = analysis.priority
    document.priority_reason = analysis.priority_reason
    document.observations = analysis.observations
    document.action_items = (
        []
        if document.document_type == "general"
        else [item.model_dump(mode="json") for item in analysis.action_items]
    )
    document.processing_status = PROCESSING_STATUSES[1]
    document.error_message = None


def _pick_title(title: str, filename: str | None, text: str, analysis: AIAnalysis) -> str:
    """User title wins, then the file name, then a short text excerpt."""
    if title and title.strip():
        return title.strip()[:255]
    if filename:
        return filename.rsplit(".", 1)[0][:255]
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:80]
    return f"{analysis.category} document"


# --- Querying ----------------------------------------------------------
def get_owned_document(db: Session, user: User, document_id: int) -> Document:
    """Fetch one document, but only if it belongs to this user."""
    document = db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    ).scalar_one_or_none()
    if document is None:
        raise not_found("Document not found.")
    return document


def list_documents(
    db: Session,
    user: User,
    *,
    search: str = "",
    category: str = "",
    priority: str = "",
    status: str = "",
    sort: str = "newest",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    """Search + filter + sort + paginate the user's documents on the server."""
    query = select(Document).where(Document.user_id == user.id)

    if search.strip():
        query = query.where(Document.title.ilike(f"%{search.strip()}%"))
    if category.strip():
        query = query.where(Document.category == category.strip())
    if priority.strip() in PRIORITIES:
        query = query.where(Document.priority == priority.strip())
    if status.strip() in PROCESSING_STATUSES:
        query = query.where(Document.processing_status == status.strip())

    total = len(db.execute(query).unique().scalars().all())

    sort_map = {
        "newest": Document.created_at.desc(),
        "oldest": Document.created_at.asc(),
        "title": Document.title.asc(),
        "priority": Document.priority.asc(),
    }
    order_by = sort_map.get(sort, Document.created_at.desc())

    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    rows = (
        db.execute(
            query.order_by(order_by).offset((page - 1) * page_size).limit(page_size)
        )
        .unique()
        .scalars()
        .all()
    )

    # Categories that actually exist for this user (used by the filter dropdown).
    categories = sorted(
        set(
            db.execute(
                select(Document.category).where(Document.user_id == user.id)
            )
            .scalars()
            .all()
        )
    )

    return {
        "items": [document_to_item(document) for document in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(math.ceil(total / page_size), 1),
        "categories": categories,
    }


def list_categories(db: Session, user: User) -> list[str]:
    """Known categories plus any category this user's documents already use."""
    existing = set(
        db.execute(select(Document.category).where(Document.user_id == user.id)).scalars().all()
    )
    return sorted(set(DOCUMENT_CATEGORIES) | existing)


# --- Update / delete ---------------------------------------------------
def update_document(db: Session, user: User, document_id: int, payload: DocumentUpdate) -> Document:
    document = get_owned_document(db, user, document_id)
    changes = payload.model_dump(exclude_unset=True)

    if "priority" in changes and changes["priority"] not in PRIORITIES:
        raise bad_request(f"priority must be one of {PRIORITIES}.")

    if "document_type" in changes and changes["document_type"] not in DOCUMENT_TYPES:
        raise bad_request(f"document_type must be one of {DOCUMENT_TYPES}.")

    for field, value in changes.items():
        setattr(document, field, value)

    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, user: User, document_id: int) -> None:
    """Delete a document. Its tasks survive but lose the link to it."""
    document = get_owned_document(db, user, document_id)

    # Keep tasks (document_id is nullable) - do this explicitly so the
    # behaviour is identical on SQLite and PostgreSQL.
    linked_tasks = db.execute(
        select(Task).where(Task.document_id == document.id)
    ).scalars().all()
    for task in linked_tasks:
        task.document_id = None

    db.delete(document)
    db.commit()
