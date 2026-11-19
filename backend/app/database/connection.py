"""Engine, session factory and the FastAPI database dependency.

WHAT THIS FILE DOES
    - creates the SQLAlchemy engine from settings.DATABASE_URL
    - creates SessionLocal (one per request in practice)
    - yields a session through `get_db()` for FastAPI dependency injection
    - enables SQLite foreign key enforcement (off by default in SQLite)

WHY IT EXISTS
    The database connection is infrastructure: it is built once and
    injected, never created inside route handlers.

HOW IT CONNECTS
    main.py               -> `app.dependency_overrides` and startup create
    routers/*.py          -> `db: Session = Depends(get_db)`
    services/*.py         -> receive that session as an argument
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# SQLite needs check_same_thread=False because FastAPI uses a thread pool.
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # verifies the connection before using it (important for Postgres)
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # noqa: ANN001
        """SQLite ignores FOREIGN KEY constraints unless this pragma is set."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one database session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
