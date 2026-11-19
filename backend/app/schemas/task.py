"""Task request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PRIORITIES, TASK_STATUSES


class TaskCreate(BaseModel):
    """Body of POST /api/tasks (manual task or converted AI action item)."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    document_id: int | None = None
    priority: str = "Medium"
    status: str = "pending"
    assigned_to: str | None = Field(default=None, max_length=120)
    due_date: date | None = None

    @field_validator("priority")
    @classmethod
    def check_priority(cls, value: str) -> str:
        if value not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}.")
        return value

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str) -> str:
        if value not in TASK_STATUSES:
            raise ValueError(f"status must be one of {TASK_STATUSES}.")
        return value


class TaskUpdate(BaseModel):
    """Body of PUT /api/tasks/{id} - every field optional.

    `clear_due_date` exists because JSON cannot distinguish
    "due_date: null" (leave unchanged) from "remove the due date".
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    priority: str | None = None
    status: str | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    due_date: date | None = None
    clear_due_date: bool = False

    @field_validator("priority")
    @classmethod
    def check_priority(cls, value: str | None) -> str | None:
        if value is not None and value not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}.")
        return value

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str | None) -> str | None:
        if value is not None and value not in TASK_STATUSES:
            raise ValueError(f"status must be one of {TASK_STATUSES}.")
        return value


class TaskOut(BaseModel):
    """Task as returned by the API (includes the linked document title)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    document_id: int | None = None
    document_title: str | None = None
    title: str
    description: str
    priority: str
    status: str
    assigned_to: str | None = None
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    page_size: int
    pages: int
    counts: dict[str, int] = Field(default_factory=dict)
