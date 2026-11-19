# =====================================================================
# DocuFlow AI - Backend image (FastAPI + Uvicorn)
#
# Build:  docker build -t docuflow-backend ./backend
# Run:    docker run -p 8001:8001 docuflow-backend
#
# Multi-stage build: the first stage installs dependencies into a
# virtual environment, the second stage only copies what is needed.
# Result: a smaller image without pip's cache and build tools.
# =====================================================================

# ---------- Stage 1: install Python dependencies ----------
FROM python:3.12-slim AS builder

# Never prompt during pip installs inside Docker
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Copy requirements first: Docker caches this layer, so dependencies are
# only reinstalled when requirements.txt actually changes.
COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# requirements.txt already includes google-genai, alembic and the
# psycopg2 PostgreSQL driver, so the image can run real AI mode and
# migrations out of the box.
RUN pip install -r requirements.txt

# ---------- Stage 2: final runtime image ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy the virtual environment built in stage 1
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Application source code (see .dockerignore for what is excluded)
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY pytest.ini .

# Run as a non-root user (security best practice)
RUN useradd --create-home --shell /bin/bash docuflow \
    && mkdir -p /app/data \
    && chown -R docuflow:docuflow /app
USER docuflow

# SQLite lives here in single-container runs (compose uses PostgreSQL)
VOLUME ["/app/data"]

EXPOSE 8001

# Health check: the container is "healthy" only when the API answers
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/api/health', timeout=4).status == 200 else 1)"

# --workers 1 keeps SQLite safe; switch to several workers only with PostgreSQL
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
