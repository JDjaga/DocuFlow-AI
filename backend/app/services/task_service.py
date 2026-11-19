"""Task business logic: CRUD with ownership and duplicate protection.

WHAT THIS FILE DOES
    create_task()        - manual task or a converted AI action item
    list_tasks()         - search + priority/status filters + due-date sort
    get/update/delete    - always scoped to the logged-in user

WHY IT EXISTS
    Keeps task rules (valid status transitions, duplicate titles for the
    same document, document ownership) in one testable place.

HOW IT CONNECTS
    routers/tasks.py             -> these functions
    routers/documents.py         -> action items are converted via create_task
    routers/dashboard.py         -> counts tasks by status
"""
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import PRIORITIES, TASK_STATUSES
from app.models.document import Document
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.errors import bad_request, not_found

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def task_to_out(task: Task) -> dict:
    """Task row -> dictionary including the linked document title."""
    return {
        "id": task.id,
        "user_id": task.user_id,
        "document_id": task.document_id,
        "document_title": task.document.title if task.document else None,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def create_task(db: Session, user: User, payload: TaskCreate) -> Task:
    """Create a task, optionally linked to one of the user's documents."""
    if payload.priority not in PRIORITIES:
        raise bad_request(f"priority must be one of {PRIORITIES}.")
    if payload.status not in TASK_STATUSES:
        raise bad_request(f"status must be one of {TASK_STATUSES}.")

    if payload.document_id is not None:
        document = db.execute(
            select(Document).where(
                Document.id == payload.document_id, Document.user_id == user.id
            )
        ).scalar_one_or_none()
        if document is None:
            raise not_found("The linked document was not found.")

        # Prevent converting the same action item twice.
        duplicate = db.execute(
            select(Task).where(
                Task.user_id == user.id,
                Task.document_id == document.id,
                Task.title == payload.title.strip(),
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise bad_request(f"Task '{payload.title}' already exists for this document.")

    task = Task(
        user_id=user.id,
        document_id=payload.document_id,
        title=payload.title.strip(),
        description=(payload.description or "").strip(),
        priority=payload.priority,
        status=payload.status,
        assigned_to=(payload.assigned_to or user.full_name),
        due_date=payload.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_owned_task(db: Session, user: User, task_id: int) -> Task:
    task = db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    ).scalar_one_or_none()
    if task is None:
        raise not_found("Task not found.")
    return task


def list_tasks(
    db: Session,
    user: User,
    *,
    search: str = "",
    priority: str = "",
    status: str = "",
    document_id: int | None = None,
    sort_by_due: str = "",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    """Filter and paginate the tasks of the current user."""
    query = select(Task).where(Task.user_id == user.id)

    if search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(Task.title.ilike(pattern) | Task.description.ilike(pattern))
    if priority.strip() in PRIORITIES:
        query = query.where(Task.priority == priority.strip())
    if status.strip() in TASK_STATUSES:
        query = query.where(Task.status == status.strip())
    if document_id is not None:
        query = query.where(Task.document_id == document_id)

    rows_all = db.execute(query).unique().scalars().all()
    total = len(rows_all)

    # Status counters for the filter tabs (computed from the same filter).
    counts = {status_name: 0 for status_name in TASK_STATUSES}
    for task in rows_all:
        counts[task.status] = counts.get(task.status, 0) + 1

    if sort_by_due == "asc":
        # NULL due dates sort last so real deadlines stay on top.
        ordered = sorted(rows_all, key=lambda task: (task.due_date is None, task.due_date))
    elif sort_by_due == "desc":
        ordered = sorted(rows_all, key=lambda task: (task.due_date is None, task.due_date), reverse=True)
    else:
        ordered = sorted(rows_all, key=lambda task: task.created_at, reverse=True)

    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    start = (page - 1) * page_size
    window = ordered[start : start + page_size]

    return {
        "items": [task_to_out(task) for task in window],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(math.ceil(total / page_size), 1),
        "counts": counts,
    }


def update_task(db: Session, user: User, task_id: int, payload: TaskUpdate) -> Task:
    task = get_owned_task(db, user, task_id)
    changes = payload.model_dump(exclude_unset=True)

    clear_due = changes.pop("clear_due_date", False)

    if "priority" in changes and changes["priority"] not in PRIORITIES:
        raise bad_request(f"priority must be one of {PRIORITIES}.")
    if "status" in changes and changes["status"] not in TASK_STATUSES:
        raise bad_request(f"status must be one of {TASK_STATUSES}.")
    if "title" in changes:
        cleaned = (changes["title"] or "").strip()
        if not cleaned:
            raise bad_request("Task title cannot be empty.")
        changes["title"] = cleaned

    if clear_due:
        task.due_date = None
    for field, value in changes.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, user: User, task_id: int) -> None:
    task = get_owned_task(db, user, task_id)
    db.delete(task)
    db.commit()
