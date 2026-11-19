"""Document endpoints: analyze, list, read, update, delete.

WHAT THIS FILE DOES
    POST   /api/documents/analyze  - file or pasted text -> AI -> stored document
    GET    /api/documents          - server side search/filter/sort/pagination
    GET    /api/documents/{id}     - one full document
    PUT    /api/documents/{id}     - edit title / category / priority / notes
    DELETE /api/documents/{id}     - delete a document

WHY IT EXISTS
    This is the heart of DocuFlow AI: the analyzer and the document
    management screen both talk to these five endpoints.

HOW IT CONNECTS
    frontend/services/documents.js -> axios calls
    services/file_service.py       -> text extraction
    services/ai_service.py         -> Mock or Gemini analysis
    services/document_service.py   -> persistence + filtering

NOTE ON THE ANALYZE ENDPOINT
    It always receives multipart/form-data: either a `file`, or a `text`
    field, plus an optional `title`. Passing `document_id` re-analyzes an
    existing document instead of creating a duplicate.
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.constants import DOCUMENT_TYPES, PRIORITIES, PROCESSING_STATUSES
from app.database.connection import get_db
from app.dependencies.authentication import get_current_user
from app.models.user import User
from app.schemas.common import Message
from app.schemas.document import AnalysisResponse, DocumentDetail, DocumentListResponse, DocumentUpdate
from app.services import document_service, file_service
from app.utils.errors import bad_request

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/analyze", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
def analyze_document(
    file: UploadFile | None = File(default=None, description="PDF or TXT file"),
    text: str | None = Form(default=None, description="Raw text when no file is uploaded"),
    title: str | None = Form(default=None, description="Optional document title"),
    document_id: int | None = Form(default=None, description="Set to re-analyze an existing document"),
    document_type: str = Form(default="task", description="task = work doc with workflow tasks, general = analysis + chat only"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Extract text, run the AI engine and store the result."""
    if file is not None and (file.filename or "").strip():
        content, original_filename = file_service.extract_text_from_upload(file)
    elif text is not None and text.strip():
        content, original_filename = file_service.extract_text_from_string(text)
    else:
        raise bad_request("Upload a PDF/TXT file or paste some text before analyzing.")

    if document_type not in DOCUMENT_TYPES:
        raise bad_request(f"document_type must be one of {DOCUMENT_TYPES}.")

    if document_id is not None:
        document = document_service.get_owned_document(db, user, document_id)
        document, provider, notice = document_service.reanalyze_document(
            db, user, document, text=content
        )
        message = "Document re-analyzed successfully."
    else:
        document, provider, notice = document_service.analyze_and_save(
            db,
            user,
            text=content,
            original_filename=original_filename,
            title=title or "",
            document_type=document_type,
        )
        message = "Document analyzed successfully."

    return AnalysisResponse(
        message=message,
        ai_provider=provider,
        ai_provider_notice=notice,
        document=document_service.document_to_detail(db, document),
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    search: str = Query(default="", max_length=255),
    category: str = Query(default="", max_length=100),
    priority: str = Query(default="", max_length=10),
    status_filter: str = Query(default="", alias="status", max_length=15),
    sort: str = Query(default="newest", pattern="^(newest|oldest|title|priority)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Paginated, filtered list of the current user's documents."""
    return document_service.list_documents(
        db,
        user,
        search=search,
        category=category,
        priority=priority,
        status=status_filter,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/categories", response_model=list[str])
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Every category the UI should offer in its filter dropdown."""
    return document_service.list_categories(db, user)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full document. Returns 404 when it belongs to somebody else."""
    document = document_service.get_owned_document(db, user, document_id)
    return document_service.document_to_detail(db, document)


@router.put("/{document_id}", response_model=DocumentDetail)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Edit user-editable fields (title, category, priority, notes)."""
    document = document_service.update_document(db, user, document_id, payload)
    return document_service.document_to_detail(db, document)


@router.delete("/{document_id}", response_model=Message)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a document. Its tasks are kept but unlinked."""
    document_service.delete_document(db, user, document_id)
    return Message(detail="Document deleted successfully.")


# Re-exported so the frontend documentation can list the valid values.
@router.get("/meta/filters", response_model=dict, include_in_schema=False)
def filter_options():
    return {"priorities": PRIORITIES, "statuses": PROCESSING_STATUSES}
