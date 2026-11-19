"""Authentication endpoints.

WHAT THIS FILE DOES
    POST /api/auth/register  - create an account and return a JWT
    POST /api/auth/login     - verify credentials and return a JWT
    GET  /api/auth/me        - return the profile of the current user

WHY IT EXISTS
    Thin HTTP layer: parse -> call auth_service -> return JSON.

HOW IT CONNECTS
    frontend/services/auth.js sends these three requests.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new account. Rejects a duplicate email with 409."""
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Verify email + password and issue an access token."""
    return auth_service.login_user(db, payload)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Return the profile behind the Bearer token (used to restore a session)."""
    return UserOut.model_validate(current_user)
