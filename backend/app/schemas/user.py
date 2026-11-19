"""User response schemas.

IMPORTANT: this file defines what the API is allowed to say about a user.
`hashed_password` is deliberately absent, so a password hash can never
leak into a JSON response by accident.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    """Public representation of a user (safe to send to the browser)."""

    model_config = ConfigDict(from_attributes=True)  # allows ORM -> Pydantic

    id: int
    full_name: str
    email: EmailStr
    created_at: datetime
