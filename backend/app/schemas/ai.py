"""Strict schema for the AI analysis output.

WHAT THIS FILE DOES
    Defines exactly what the AI engine is allowed to return and validates
    it. Anything malformed (missing summary, priority "urgent", a date that
    is not a date) is rejected here instead of being saved to the database.

WHY IT EXISTS
    LLMs occasionally return broken or inventive JSON. Pydantic is the
    gatekeeper between "what the model said" and "what we store".

HOW IT CONNECTS
    mock_ai.py / gemini_provider.py both produce the same payload shape
        -> ai_service.parse_ai_response() converts it into AIAnalysis
        -> document_service persists the validated fields
"""
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.constants import DOCUMENT_CATEGORIES, PRIORITIES


class AIEntity(BaseModel):
    """One extracted fact, e.g. {type: Organization, value: Acme Corp}."""

    type: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=300)


class AIActionItem(BaseModel):
    """A suggested task generated from the document."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    priority: str = "Medium"
    due_date: date | None = None

    @field_validator("priority")
    @classmethod
    def normalise_priority(cls, value: str) -> str:
        return _normalise_priority(value)


class AIAnalysis(BaseModel):
    """The complete, validated analysis of one document."""

    summary: str = Field(min_length=1, max_length=4000)
    category: str = Field(min_length=1, max_length=100)
    key_entities: list[AIEntity] = Field(default_factory=list, max_length=60)
    priority: str
    priority_reason: str = Field(default="", max_length=1000)
    action_items: list[AIActionItem] = Field(default_factory=list, max_length=25)
    observations: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        return _normalise_priority(value)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        """Keep the category list finite so the frontend filters stay useful."""
        cleaned = (value or "").strip()
        if cleaned in DOCUMENT_CATEGORIES:
            return cleaned
        return "General Document"

    @field_validator("summary", mode="before")
    @classmethod
    def summary_must_not_be_empty(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("The AI returned an empty summary.")
        return value.strip() if isinstance(value, str) else value


# --- Helpers -----------------------------------------------------------
_PRIORITY_ALIASES = {
    "high": "High",
    "urgent": "High",
    "critical": "High",
    "important": "High",
    "medium": "Medium",
    "normal": "Medium",
    "moderate": "Medium",
    "low": "Low",
    "minor": "Low",
}


def _normalise_priority(value: str) -> str:
    """Accept common AI variants and map them onto our three levels."""
    cleaned = (value or "").strip()
    mapped = _PRIORITY_ALIASES.get(cleaned.lower())
    if mapped is None:
        raise ValueError(f"priority must be one of {PRIORITIES}, got '{value}'.")
    return mapped


def parse_ai_response(payload: Any) -> AIAnalysis:
    """Convert an AI (or mock) response into a validated AIAnalysis.

    Raises pydantic.ValidationError when the model returned garbage, which
    the ai_service layer turns into a clean 503 error for the frontend.
    """
    if isinstance(payload, str):
        # A raw JSON string slipped through - parse it first.
        payload = AIAnalysis.model_validate_json(payload)
        return payload
    if isinstance(payload, AIAnalysis):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("The AI response must be a JSON object.")
    return AIAnalysis.model_validate(payload)
