"""Pydantic schemas (the API's request/response contract)."""
from app.schemas.ai import AIAnalysis, AIActionItem, AIEntity
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import Message, PageMeta
from app.schemas.document import (
    AnalysisResponse,
    AnalyzeTextRequest,
    DocumentDetail,
    DocumentListItem,
    DocumentListResponse,
    DocumentUpdate,
)
from app.schemas.task import TaskCreate, TaskListResponse, TaskOut, TaskUpdate
from app.schemas.user import UserOut

__all__ = [
    "AIAnalysis",
    "AIActionItem",
    "AIEntity",
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "Message",
    "PageMeta",
    "AnalysisResponse",
    "AnalyzeTextRequest",
    "DocumentDetail",
    "DocumentListItem",
    "DocumentListResponse",
    "DocumentUpdate",
    "TaskCreate",
    "TaskListResponse",
    "TaskOut",
    "TaskUpdate",
    "UserOut",
]
