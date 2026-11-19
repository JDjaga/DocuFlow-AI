"""Chat-with-document service.

WHAT THIS FILE DOES
    answer_question() takes a user's question plus a document id, verifies
    ownership, then asks the CENTRALIZED provider manager to answer.

    When the document has compatible stored embeddings (RAG), only the
    top retrieved excerpts are sent - with honest source citations.
    Otherwise the full extracted text is used (existing behaviour).

WHY IT EXISTS
    This is the "chat with your documents" feature. The AI never sees other
    users' data: the document is loaded through get_owned_document(), so a
    guessed id returns 404 exactly like the document endpoints.

HOW IT CONNECTS
    routers/chat.py -> chat_service.answer_question()
                     -> document_service.get_owned_document()
                     -> rag_service.retrieve_for_document()  (RAG path)
                     -> provider_manager.execute("answer_question")
                        -> gemini | openrouter | ollama | mock

INTERVIEW NOTE
    "Chat is a thin layer over the same provider boundary as analysis -
     context is the stored extracted text (or retrieved excerpts), the
     answer is plain text, and ownership is enforced before a single
     token is sent to any provider."
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.user import User
from app.services import document_service, rag_service
from app.services.ai import get_provider_manager
from app.utils.errors import bad_request, service_unavailable

#: returned as (answer, provider, fallback_notice, sources)
ChatOutcome = tuple[str, str, str | None, list[dict]]


def answer_question(db: Session, user: User, document_id: int, question: str) -> ChatOutcome:
    """Answer `question` about one owned document.

    Returns:
        (answer_text, provider_label, fallback_notice, sources)
        where provider is 'gemini' | 'openrouter' | 'ollama' | 'mock',
        fallback_notice is None unless a fallback really happened, and
        sources lists the retrieved chunks (empty for full-text answers).
    """
    question = question.strip()
    if len(question) < 3:
        raise bad_request("Please type a question with at least 3 characters.")

    document = document_service.get_owned_document(db, user, document_id)

    if document.processing_status != "completed" or not document.extracted_text.strip():
        raise bad_request("This document has no analyzed text to chat with yet.")

    # --- RAG path: retrieve the top chunks of THIS document -------------
    retrieval = rag_service.retrieve_for_document(db, user, document, question)
    if retrieval is not None:
        outcome = rag_service.answer_from_context(retrieval, question)
        sources = retrieval.sources
    else:
        # --- Full-document path (existing behaviour) --------------------
        text = document.extracted_text[: settings.MAX_INPUT_CHARS]
        outcome = get_provider_manager().execute(
            "answer_question",
            lambda provider: provider.answer_question(text, question),
        )
        sources = []

    answer = _clean_answer(outcome.result.data)
    if not answer:
        raise service_unavailable("The AI returned an empty answer. Please try again.")
    return answer, outcome.result.provider, outcome.notice, sources


def _clean_answer(answer: str) -> str:
    """Normalise provider output: strip markdown fences and collapse blanks."""
    cleaned = str(answer).strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("text"):
            cleaned = cleaned[4:]
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
