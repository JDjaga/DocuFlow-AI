"""Document chat endpoints: ask questions about a stored document.

WHAT THIS FILE DOES
    POST /api/documents/{document_id}/chat - answer a question using only
    that document's extracted text (Mock AI or Gemini).

WHY IT EXISTS
    Users can upload dozens of documents; chat lets them query one without
    re-reading it. Ownership is enforced in the service layer, so users can
    never chat with somebody else's document.

HOW IT CONNECTS
    frontend/services/chat.js -> this router -> chat_service -> AI provider
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api/documents", tags=["Chat"])


@router.post("/{document_id}/chat", response_model=ChatResponse)
def chat_with_document(
    document_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Answer a question about the document's extracted text."""
    answer, provider, notice, sources = chat_service.answer_question(
        db, user, document_id, payload.question
    )
    return ChatResponse(
        document_id=document_id,
        question=payload.question.strip(),
        answer=answer,
        provider=provider,
        provider_notice=notice,
        sources=sources,
    )
