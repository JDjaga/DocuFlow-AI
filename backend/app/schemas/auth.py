"""Authentication request/response schemas."""
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.user import UserOut

PASSWORD_MIN_LENGTH = 8


class RegisterRequest(BaseModel):
    """Body of POST /api/auth/register."""

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    confirm_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @model_validator(mode="after")
    def passwords_must_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    """Body of POST /api/auth/login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Returned after a successful login/register."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserProfile(BaseModel):
    """Body of PUT-style profile updates (kept for completeness)."""

    model_config = ConfigDict(from_attributes=True)

    full_name: str = Field(min_length=2, max_length=120)
