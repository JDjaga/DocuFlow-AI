"""Authentication business logic.

WHAT THIS FILE DOES
    register_user()  - rejects duplicates, hashes the password, returns a token
    login_user()     - verifies credentials, returns a token
    get_current_*    - small user lookups used by routers

WHY IT EXISTS
    Routers stay thin: they receive validated data, call one function and
    return its result. All rules (unique email, password check) live here.

HOW IT CONNECTS
    routers/auth.py  -> this file
    core/security.py -> hashing + JWT creation
    models/user.py   -> the table being written
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserOut
from app.utils.errors import conflict, unauthorized

INVALID_CREDENTIALS = "Invalid email or password."


def _normalise_email(email: str) -> str:
    """Emails are stored lowercase so 'A@b.com' and 'a@b.com' are one account."""
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == _normalise_email(email))).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def _issue_token(user: User) -> TokenResponse:
    token = create_access_token(subject=str(user.id), extra_claims={"email": user.email})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


def register_user(db: Session, payload: RegisterRequest) -> TokenResponse:
    """Create an account and immediately return a login token."""
    if get_user_by_email(db, payload.email) is not None:
        raise conflict("An account with this email already exists.")

    user = User(
        full_name=payload.full_name.strip(),
        email=_normalise_email(payload.email),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()  # flushes the new id onto `user`
    db.refresh(user)
    return _issue_token(user)


def login_user(db: Session, payload: LoginRequest) -> TokenResponse:
    """Verify email + password and return a token."""
    user = get_user_by_email(db, payload.email)
    # Same message for "unknown email" and "wrong password" so the API
    # cannot be used to discover which emails are registered.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise unauthorized(INVALID_CREDENTIALS)
    return _issue_token(user)
