"""Task endpoints (full CRUD).

WHAT THIS FILE DOES
    POST   /api/tasks       - create a manual task or a converted AI action item
    GET    /api/tasks       - search + filters + due-date sorting + pagination
    GET    /api/tasks/{id}  - one task
    PUT    /api/tasks/{id}  - edit title/description/priority/status/due date
    DELETE /api/tasks/{id}  - delete a task

WHY IT EXISTS
    Turns analysis output into tracked work - the "decisions" part of
    "Turn documents into decisions".

HOW IT CONNECTS
    frontend/services/tasks.js -> these endpoints
    services/task_service.py   - ownership, validation, duplicate checks
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.constants import PRIORITIES, TASK_STATUSES
from app.database.connection import get_db
from app.dependencies.authentication import get_current_user
from app.models.user import User
from app.schemas.common import Message
from app.schemas.task import TaskCreate, TaskListResponse, TaskOut, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a task. `document_id` links it to one of your documents."""
    task = task_service.create_task(db, user, payload)
    return task_service.task_to_out(task)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    search: str = Query(default="", max_length=255),
    priority: str = Query(default="", max_length=10),
    status_filter: str = Query(default="", alias="status", max_length=15),
    document_id: int | None = Query(default=None),
    sort_by_due: str = Query(default="", pattern="^(|asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Paginated, filtered list of the current user's tasks."""
    return task_service.list_tasks(
        db,
        user,
        search=search,
        priority=priority,
        status=status_filter,
        document_id=document_id,
        sort_by_due=sort_by_due,
        page=page,
        page_size=page_size,
    )


@router.get("/meta/filters", response_model=dict, include_in_schema=False)
def filter_options():
    return {"priorities": PRIORITIES, "statuses": TASK_STATUSES}


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One task. 404 if it does not exist or is not yours."""
    task = task_service.get_owned_task(db, user, task_id)
    return task_service.task_to_out(task)


@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Partial update: only the fields present in the body are changed."""
    task = task_service.update_task(db, user, task_id, payload)
    return task_service.task_to_out(task)


@router.delete("/{task_id}", response_model=Message)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a task."""
    task_service.delete_task(db, user, task_id)
    return Message(detail="Task deleted successfully.")
