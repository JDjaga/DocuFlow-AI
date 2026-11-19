"""Alembic environment - connects migrations to the SQLAlchemy models.

WHAT THIS FILE DOES
    - reads DATABASE_URL from the same configuration the app uses
    - imports every model so Alembic can compare code vs. database
    - runs migrations in online mode (against the real database)

WHY IT EXISTS
    Alembic is how real projects evolve a database schema without
    deleting data. DocuFlow AI starts with `create_all`, and this file
    is ready for every schema change after that.

COMMON COMMANDS (run from backend/)
    alembic revision --autogenerate -m "describe the change"
    alembic upgrade head
    alembic downgrade -1
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.database.base import Base
from app import models  # noqa: F401 - registers User, Document and Task

config = context.config

# Point Alembic at the exact same database as the running application.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without touching the database (useful for review)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations to the configured database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
