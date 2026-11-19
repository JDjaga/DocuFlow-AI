"""Document request/response schemas."""
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Requests ----------------------------------------------------------
class AnalyzeTextRequest(BaseModel):
    """Body of POST /api/documents/analyze when raw text is pasted."""
    title: str = Field(default="", max_length=255)
    text: str = Field(min_length=1, max_length=100000)


class DocumentUpdate(BaseModel):
    """Body of PUT /api/documents/{id} - only fields the user may edit."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    priority: str | None = None
    user_notes: str | None = Field(default=None, max_length=5000)
    document_type: str | None = None


# --- Responses ---------------------------------------------------------
class DocumentListItem(BaseModel):
    """Compact representation used in tables and the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_filename: str | None = None
    category: str
    document_type: str = "task"
    priority: str
    priority_reason: str = ""
    processing_status: str
    created_at: datetime
    updated_at: datetime


class DocumentDetail(BaseModel):
    """Full document returned by GET /api/documents/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    original_filename: str | None = None
    category: str
    document_type: str = "task"
    priority: str
    priority_reason: str
    processing_status: str
    error_message: str | None = None
    summary: str
    key_entities: list[dict[str, Any]]
    action_items: list[dict[str, Any]]
    observations: list[str]
    extracted_text: str
    user_notes: str
    task_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int
    pages: int
    categories: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    """Returned by POST /api/documents/analyze after a successful run."""

    message: str
    ai_provider: str
    ai_provider_notice: str | None = None  # set only on automatic fallback
    document: DocumentDetail


class ActionItemOut(BaseModel):
    """AI action item, shaped for the frontend before it becomes a Task."""

    title: str
    description: str = ""
    priority: str = "Medium"
    due_date: date | None = None
