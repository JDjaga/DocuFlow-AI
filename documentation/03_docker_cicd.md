# DocuFlow AI — Docker & CI/CD

> **Document 3 of 6** · [Architecture](01_project_architecture.md) · [Code Concepts](02_code_concepts_explained.md) · [Interview Q&A](04_interview_qa.md) · [Checklist](05_verification_checklist.md) · [AI Providers](06_ai_providers.md)

This document explains **how to run DocuFlow AI with Docker**, what each container does, and how the GitHub Actions pipeline protects the codebase.

---

## 1. Two ways to run the project

| | Local development | Docker (production-like) |
|---|---|---|
| Frontend | Vite dev server, hot reload | Nginx serving built files |
| Backend | Uvicorn with `--reload` | Uvicorn, 1 worker, non-root |
| Database | **SQLite** file (`backend/docuflow.db`) | **PostgreSQL 16** in a volume |
| URL | http://localhost:5173 | http://localhost:8080 |
| Best for | writing code | demos, CI, deployments |

Both use the **same code** — only environment variables differ. That is the whole point of `app/core/config.py`.

---

## 2. Quick start — Docker

```bash
# 1. from the project root (the folder containing docker-compose.yml)
cp .env.example .env          # then edit SECRET_KEY and POSTGRES_PASSWORD

# 2. build and start all three containers
docker compose up --build

# 3. wait for the healthchecks (first build takes a few minutes)
docker compose ps
#   NAME        STATUS               PORTS
#   frontend    Up (healthy)         0.0.0.0:8080->80/tcp
#   backend     Up (healthy)         0.0.0.0:8001->8001/tcp
#   db          Up (healthy)         5432/tcp

# 4. open the app
#    Frontend:  http://localhost:8080
#    API docs:  http://localhost:8001/docs
```

Stop and clean up:

```bash
docker compose down          # stop containers, KEEP the database volume
docker compose down -v       # stop and DELETE the database (fresh start)
docker compose logs -f backend   # follow the API logs
```

> **Note the ports:** frontend **8080**, backend **8001**. Nothing uses port 8000.

---

## 3. What each file does

### 3.1 `backend/Dockerfile`

```
Stage "builder"                Stage "runtime"
─────────────────              ─────────────────
python:3.12-slim                python:3.12-slim
pip install → /opt/venv   ───▶  COPY --from=builder /opt/venv
                                COPY app/, alembic/, alembic.ini
                                useradd docuflow  → USER docuflow
                                EXPOSE 8001
                                HEALTHCHECK → GET /api/health
                                CMD uvicorn app.main:app --port 8001
```

**Why multi-stage?** The builder stage contains pip's cache and compiler leftovers. Only the virtualenv and source code move to the final image, which is smaller and has less attack surface.

**Why `USER docuflow`?** A container running as root that is later compromised gives the attacker root inside the container. A non-root user limits the damage.

**Why `--workers 1`?** SQLite (single-container runs) does not handle multiple writers well. Switch to `--workers 4` only when `DATABASE_URL` points at PostgreSQL.

**Dependency note:** `requirements.txt` includes everything the image needs — `google-genai`, `pdfplumber` (layout-aware PDF extraction with pypdf fallback), `psycopg2-binary` (PostgreSQL) and `alembic` — so the image supports real AI mode and migrations out of the box.

### 3.2 `frontend/Dockerfile`

```
Stage "build" (node:22-alpine)        Stage "runtime" (nginx:1.27-alpine)
─────────────────────────────         ────────────────────────────────────
npm ci (cached layer)                 COPY nginx.conf → conf.d/default.conf
npm run build  →  dist/          ───▶ COPY --from=build /app/dist → html/
                                     EXPOSE 80, HEALTHCHECK → wget /
```

The Node toolchain never ships to production — only its `dist/` output does.

### 3.3 `frontend/nginx.conf`

Four jobs in ~60 lines:

| Job | Directive | Why |
|---|---|---|
| Serve the SPA | `try_files $uri $uri/ /index.html;` | React Router owns `/tasks` etc. — a hard refresh must return `index.html`, not 404 |
| Proxy the API | `location /api/ → http://backend:8001` | Browser sees **one origin** (8080) → no CORS, backend URL hidden |
| Cache assets | `expires 30d; immutable` | Vite hashes filenames (`index-BLZP-8EQ.js`), so 30-day caching is safe |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` | Basic hardening for free |

Two tuning values worth knowing:

```nginx
client_max_body_size 12m;   # > MAX_FILE_SIZE_MB (10) so uploads never 413
proxy_read_timeout 120s;    # > AI_REQUEST_TIMEOUT (60) so analysis never 504s at the proxy
```

**Why proxy instead of a separate API domain?** A second origin (`api.example.com`) forces CORS configuration, preflight `OPTIONS` requests, and credential rules. One origin behind one proxy removes all of it.

### 3.4 `docker-compose.yml`

```yaml
services:
  db:       postgres:16-alpine   # NOT published to the host
  backend:  build ./backend      # depends_on db (healthy) · port 8001
  frontend: build ./frontend     # depends_on backend (healthy) · port 8080
```

**Startup order is enforced by healthchecks**, not by `depends_on` alone:

```
db healthy (pg_isready)  →  backend starts  →  backend healthy (/api/health)  →  frontend starts
```

Without healthchecks, `depends_on` only waits for the container to *start*, and the backend would crash trying to reach PostgreSQL before it accepts connections.

**The database has no published port.** Only containers on the compose network can reach `db:5432`. Uncomment the `ports` block if you need `psql` access from your machine.

### 3.5 `.env.example`

```bash
SECRET_KEY=change-me-to-a-long-random-string   # JWT signing key — MUST change
POSTGRES_PASSWORD=docuflow_dev_password
MOCK_AI=true                                   # false -> AI_PROVIDER_PRIORITY chain
GEMINI_API_KEY=                                # primary real provider (see 06_ai_providers.md)
AI_PROVIDER_PRIORITY=gemini,openrouter,ollama
APP_VERSION=1.0.0
```

Generate a real secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Compose reads `.env` automatically for `${VAR}` substitutions; the backend receives them through `environment:`. `.env` is git-ignored — only `.env.example` is committed.

---

## 4. How the request flows in Docker

```
Browser
  │  GET http://localhost:8080/api/documents
  ▼
┌──────────────────────────┐
│ frontend (nginx :8080)   │  location /api/ → proxy_pass http://backend:8001
│  - serves index.html     │
│  - serves /assets/*.js   │
└────────────┬─────────────┘
             │  docker network: backend:8001
             ▼
┌──────────────────────────┐
│ backend (uvicorn :8001)  │  JWT check → SQLAlchemy
└────────────┬─────────────┘
             │  docker network: db:5432
             ▼
┌──────────────────────────┐
│ db (postgres:16)         │  volume: postgres_data
└──────────────────────────┘
```

Nothing outside the compose network can touch PostgreSQL.

---

## 5. Useful Docker commands

```bash
# rebuild only one service after code changes
docker compose up -d --build backend

# run the test suite inside a throwaway container
docker compose run --rm backend pytest --tb=short -q

# one-off psql session (after temporarily publishing port 5432)
docker compose exec db psql -U docuflow -d docuflow

# inspect health
docker inspect --format='{{.State.Health.Status}}' $(docker compose ps -q backend)

# free space
docker image prune -a
```

---

## 6. GitHub Actions CI

**File:** `.github/workflows/ci.yml`

```
             push / pull_request → main|master
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
  backend-tests                 frontend-build
  ubuntu-latest                 ubuntu-latest
  Python 3.12 (pip cache)       Node 22 (npm cache)
  pip install -r requirements   npm ci
  pytest --tb=short -q          npm run build
  upload report on failure      upload dist/ (7 days)
        │                             │
        └──────────────┬──────────────┘
                       ▼
              workflow fails if EITHER job fails
```

### Why these two jobs

| Job | Proves |
|---|---|
| `backend-tests` | all **142** tests still pass (auth, isolation, validation, AI contract, document types, chat/RAG) |
| `frontend-build` | the React app still compiles for production — catches broken imports and JSX typos that a linter would miss |

A build step is the cheapest frontend "test": most beginner-breaking mistakes (`import x from './wrongPath'`) fail there instantly.

### Design details worth mentioning in an interview

1. **No secrets in CI.** Tests run in Mock AI mode with a temporary SQLite database — nothing to configure.
2. **`concurrency` + `cancel-in-progress`.** Pushing twice quickly cancels the obsolete run instead of wasting minutes.
3. **Dependency caching.** `setup-python`'s `cache: pip` and `setup-node`'s `cache: npm` key on the lock/requirements files, so unchanged dependencies are never re-downloaded.
4. **`defaults.run.working-directory`.** No `cd backend &&` sprinkled on every step.
5. **Artifacts only when useful.** The pytest report uploads *only on failure*; the built `dist/` is kept 7 days for inspection.
6. **Failure isolation.** Each job has its own `working-directory`, so a frontend syntax error never hides backend test results.

### Adding a third job later

```yaml
  docker-build:
    name: Docker image builds
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t docuflow-backend ./backend
      - run: docker build -t docuflow-frontend ./frontend
```

A natural next step once the pipeline is green: add a `deploy` job gated on `if: github.ref == 'refs/heads/main'`.

---

## 7. Deploying to Render (`render.yaml`)

The repo ships a **Render Blueprint** at the project root. Render reads it and
provisions two services from one repo:

| Service | Type | Build | Notes |
|---|---|---|---|
| `docuflow-backend` | Web Service (Python) | `pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; health check `GET /api/health` |
| `docuflow-frontend` | Static Site (Node) | `npm ci && npm run build` | SPA rewrites → `index.html`; `VITE_API_URL` baked at build time |

**Env vars:** non-secret values are pre-filled in `render.yaml`
(`AI_PROVIDER_PRIORITY`, `OPENROUTER_FREE_MODELS_ONLY=true`, limits…).
Anything marked `sync: false` — `SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`,
`OPENROUTER_API_KEY`, `VITE_API_URL` — is entered once in the Render
dashboard and never touches git.

**Database:** Render's free web service has an ephemeral filesystem, so use a
managed Postgres (Neon/Supabase free tier) and set `DATABASE_URL` to its
connection string. `Base.metadata.create_all()` builds the schema on first
boot; for an existing database run `alembic upgrade head` in `backend/`.

**Flow:** GitHub repo → Render → New → Blueprint → pick repo → fill secrets →
deploy. Every push to `main` redeploys automatically (that is the "CD" half —
GitHub Actions is the "CI" half; they are complementary, not duplicates).

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `backend` restarts, log shows `password authentication failed` | Postgres not ready yet | `docker compose up -d db` then `docker compose up -d` |
| `frontend` healthy but app shows "Cannot reach the server" | backend unhealthy | `docker compose logs backend` |
| `413 Request Entity Too Large` | upload > Nginx limit | raise `client_max_body_size` (already 12m) |
| `504` on analysis in Docker only | proxy timeout < AI timeout | `proxy_read_timeout` is already 120s (> `AI_REQUEST_TIMEOUT=60`) |
| Blank page after deploy | missing SPA fallback | `try_files ... /index.html` must be present |
| `port is already allocated` | something on 8080/8001 | `docker compose down` or change the host side, e.g. `"8081:8080"` |
| Want a clean database | old volume | `docker compose down -v` |

---

## 9. Security checklist (Docker)

- [x] Non-root user in the backend image
- [x] Multi-stage builds (no compilers or pip cache in runtime images)
- [x] PostgreSQL port not published
- [x] Secrets supplied via `.env`, git-ignored, never baked into images
- [x] Healthchecks so a broken container is detected, not silently rotated
- [x] `restart: unless-stopped` for self-healing
- [x] Nginx security headers
- [ ] **Your job:** set a strong `SECRET_KEY` and `POSTGRES_PASSWORD` before any real deployment
- [ ] **Your job:** terminate TLS in front of Nginx (Caddy/Traefik/Cloudflare)

---

## 10. CI/CD vocabulary this project demonstrates

| Term | Where it appears here |
|---|---|
| **CI** | GitHub Actions running tests + build on every push |
| **Pipeline** | the two jobs in `ci.yml` |
| **Healthcheck** | `/api/health` polled by Docker and Compose |
| **Immutable artifacts** | hashed Vite filenames cached for 30 days |
| **Caching** | pip/npm caches keyed on lock files |
| **Concurrency control** | `cancel-in-progress` on superseded runs |
| **Non-root execution** | `USER docuflow` |
| **Dependency graph** | `depends_on: condition: service_healthy` |
| **Infrastructure as code** | the entire stack is described in `docker-compose.yml` |
| **CD** | *(not yet implemented — see §6 for the natural next step)* |

---

*Continue with [04 — Interview Q&A](04_interview_qa.md).*
