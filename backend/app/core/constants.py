"""Shared constants used by models, schemas, services and routers.

WHAT THIS FILE DOES
    Central place for the fixed vocabulary of the application
    (priorities, statuses, categories) and a small list of the most
    common document categories.

WHY IT EXISTS
    The words "pending" / "in_review" / "completed" must mean exactly
    the same thing everywhere. One file = no typos, no drift.

HOW IT CONNECTS
    models/*.py      -> column defaults and index hints
    schemas/*.py     -> Literal types used for request validation
    services/*.py    -> filtering and mock AI generation
"""
from typing import Literal

# --- Enums expressed as Literal types (validated by Pydantic) ---------
Priority = Literal["High", "Medium", "Low"]
TaskStatus = Literal["pending", "in_review", "completed"]
ProcessingStatus = Literal["pending", "completed", "failed"]
DocumentType = Literal["task", "general"]

PRIORITIES: list[str] = ["High", "Medium", "Low"]
TASK_STATUSES: list[str] = ["pending", "in_review", "completed"]
PROCESSING_STATUSES: list[str] = ["pending", "completed", "failed"]

# "task" -> work document: analysis + action items + workflow tasks
# "general" -> reference document: analysis + chat only, no tasks
DOCUMENT_TYPES: list[str] = ["task", "general"]

# --- Document categories (also used by the Mock AI engine) ------------
DOCUMENT_CATEGORIES: list[str] = [
    "Business Proposal",
    "Meeting Notes",
    "Technical Report",
    "Financial Document",
    "Customer Feedback",
    "Project Report",
    "General Document",
]

# --- Keywords the Mock AI uses to guess a category --------------------
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Business Proposal": ["proposal", "scope of work", "quotation", "pricing", "bid", "partnership"],
    "Meeting Notes": ["agenda", "minutes of meeting", "attendees", "meeting held", "action points"],
    "Technical Report": ["architecture", "api", "database", "deployment", "bug", "performance", "system"],
    "Financial Document": ["invoice", "payment", "budget", "revenue", "tax", "cost", "billing"],
    "Customer Feedback": ["feedback", "complaint", "customer", "review", "satisfaction", "support ticket"],
    "Project Report": ["milestone", "timeline", "deliverable", "sprint", "project status", "gantt"],
}

# --- Files the analyzer accepts ---------------------------------------
ALLOWED_EXTENSIONS: list[str] = [".pdf", ".txt"]

# --- Extensions that must appear at the very start of a real file -----
FILE_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
}
