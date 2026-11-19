"""Pytest configuration: isolated test database + shared fixtures.

WHAT THIS FILE DOES
    1. points the app at a temporary SQLite database BEFORE the app loads
    2. switches on Mock AI so tests never need an API key or network
    3. removes the demo animation delay so the suite stays fast
    4. cleans every table between tests so they cannot influence each other

HOW TO RUN
    cd backend
    pytest -q
"""
import os
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# IMPORTANT: this environment setup must happen before `app` is imported,
# otherwise config.py would already have read the developer's real .env.
# ---------------------------------------------------------------------------
_TEST_DB = Path(tempfile.gettempdir()) / "docuflow_ai_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["MOCK_AI"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-never-used-in-production"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
# Deterministic offline embeddings: no keys, no network, no downloads.
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["AI_MAX_RETRIES"] = "0"      # keep failure paths fast in tests
os.environ["AI_REQUEST_TIMEOUT"] = "10"

# ---------------------------------------------------------------------------
# Hermetic AI configuration: config.py reads backend/.env by absolute path,
# and a developer's .env may contain REAL provider keys. Environment
# variables always beat the .env file in pydantic-settings, so masking them
# here guarantees the suite runs in offline mock mode with zero network
# calls and zero cost, no matter what is in .env.
# ---------------------------------------------------------------------------
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_MODEL"] = "gemini-1.5-flash"
os.environ["AI_PROVIDER_PRIORITY"] = "gemini,openrouter,ollama"
os.environ["AI_FALLBACK_ENABLED"] = "true"
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["OPENROUTER_MODEL"] = ""
os.environ["OPENROUTER_FALLBACK_MODELS"] = ""
os.environ["OPENROUTER_ALLOWED_MODELS"] = ""
os.environ["OPENROUTER_FREE_MODELS_ONLY"] = "true"
os.environ["OPENROUTER_MAX_SPEND"] = "0"
os.environ["OLLAMA_ENABLED"] = "false"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.connection import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import mock_ai  # noqa: E402

# Tests must not sleep for the frontend processing animation.
mock_ai.MOCK_DELAY_SECONDS = 0.0


# --- Helpers ------------------------------------------------------------
def _clean_tables() -> None:
    """Delete every row so each test starts from an empty database."""
    session = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


def make_pdf(text: str) -> bytes:
    """Build a tiny but valid one-page PDF containing `text`.

    Writing the file by hand (with correct xref offsets) lets the test
    suite verify real PDF extraction without adding another dependency.
    """
    safe_text = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 12 Tf 50 720 Td ({safe_text}) Tj ET".encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_start = len(output)
    output += f"xref\n0 {len(objects) + 1}\n".encode()
    output += b"0000000000 65535 f \n"
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF"
    ).encode()
    return bytes(output)


# --- Fixtures -----------------------------------------------------------
@pytest.fixture()
def client():
    """A fresh FastAPI test client with an empty database per test."""
    Base.metadata.create_all(bind=engine)
    _clean_tables()
    with TestClient(app) as test_client:
        yield test_client
    _clean_tables()


@pytest.fixture()
def db():
    """A direct database session (used for low-level assertions)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def register_user():
    """Factory that registers a user and returns their auth headers."""

    def _register(
        client: TestClient,
        email: str = "user@example.com",
        password: str = "Secret123!",
        full_name: str = "Test User",
    ) -> dict:
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": full_name,
                "email": email,
                "password": password,
                "confirm_password": password,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {
            "headers": {"Authorization": f"Bearer {body['access_token']}"},
            "user": body["user"],
        }

    return _register


@pytest.fixture()
def sample_text() -> str:
    """A realistic document used by the analysis tests."""
    return (
        "Business Proposal from Acme Technologies Ltd.\n\n"
        "Dear Dr. Sharma, please review the proposed project scope and budget. "
        "The urgent deadline for submitting the bid is 2026-12-01 and the total "
        "cost is USD 45,000. Contact us at proposals@acmetech.com or +91 98765 43210. "
        "We must ensure the deliverables are signed off before the end of the month. "
        "Reference: PROJ-2026-118."
    )
