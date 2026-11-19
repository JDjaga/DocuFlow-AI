"""User table.

WHAT THIS FILE DOES
    Defines the `users` table: identity + credentials.

WHY IT EXISTS
    Every document and task belongs to exactly one user, so ownership
    checks start here.

HOW IT CONNECTS
    auth_service.py       -> creates/reads users
    document/task models  -> foreign key to users.id
    schemas/user.py       -> turns this row into a safe JSON response
                             (hashed_password is NEVER included)
"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    # Relationships (one user -> many documents / tasks)
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # useful while debugging in a Python shell
        return f"<User id={self.id} email={self.email}>"
