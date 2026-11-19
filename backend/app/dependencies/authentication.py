"""Authentication dependency used by every protected endpoint.

WHAT THIS FILE DOES
    Extracts the `Authorization: Bearer <token>` header, validates the
    JWT, loads the matching user and returns it.

WHY IT EXISTS
    One line in a router (`user: User = Depends(get_current_user)`)
    protects an endpoint. There is no way to forget the check.

HOW IT CONNECTS
    routers/documents.py, tasks.py, dashboard.py all depend on
    `get_current_user`. It uses security.decode_access_token and the
    database session from connection.get_db.

INTERVIEW NOTE
    "Ownership is enforced in the service layer as well - the user id is
     passed into every query, so changing the id in the URL cannot expose
     another user's data."
"""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.user import User
from app.utils.errors import unauthorized

# tokenUrl only documents where to get a token (used by /docs Swagger UI).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

CREDENTIALS_ERROR = "Could not validate credentials. Please log in again."


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user or raise 401."""
    payload = decode_access_token(token)
    if not payload:
        raise unauthorized(CREDENTIALS_ERROR)

    user_id = payload.get("sub")
    if not user_id or not str(user_id).isdigit():
        raise unauthorized(CREDENTIALS_ERROR)

    user = db.get(User, int(user_id))
    if user is None:
        # Token is signed correctly but the account no longer exists
        # (deleted). Treat it as an authentication failure, NOT a 404:
        # 401 makes the frontend interceptor clear the stale token and
        # send the user to /login instead of leaving them stuck.
        raise unauthorized(CREDENTIALS_ERROR)
    return user
