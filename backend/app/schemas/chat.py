"""Chat-with-document schemas.

WHAT THIS FILE DOES
    Defines the request/response shape for POST /api/documents/{id}/chat.

WHY IT EXISTS
    The chat endpoint answers questions using ONLY the stored text of one
    document. Keeping the contract in Pydantic means the question length
    is validated before it ever reaches an AI provider.

ADDED BY THE MULTI-PROVIDER UPGRADE (backward compatible)
    provider_notice - set only when automatic fallback happened
    sources         - retrieved chunk citations (empty for full-text)
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Body of POST /api/documents/{document_id}/chat."""

    question: str = Field(min_length=3, max_length=2000)


class ChatSource(BaseModel):
    """One retrieved chunk cited by the answer (never invented)."""

    chunk_index: int
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    """Answer returned to the chat panel."""

    document_id: int
    question: str
    answer: str
    provider: str  # 'mock' | 'gemini' | 'openrouter' | 'ollama'
    provider_notice: str | None = None  # fallback notice, e.g. "Google Gemini quota was exhausted..."
    sources: list[ChatSource] = Field(default_factory=list)
