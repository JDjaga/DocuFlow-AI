# DocuFlow AI — Project Architecture

> **Document 1 of 6** · [Code Concepts](02_code_concepts_explained.md) · [Docker & CI/CD](03_docker_cicd.md) · [Interview Q&A](04_interview_qa.md) · [Checklist](05_verification_checklist.md) · [AI Providers](06_ai_providers.md)

This document explains **how DocuFlow AI is put together** and *why* each piece exists. Read it top-to-bottom once and you will understand the whole system.

---

## 1. One-paragraph overview

DocuFlow AI is a full-stack SaaS that turns documents into decisions. A user signs up, uploads a PDF/TXT (or pastes text), picks a **document type** — *task/work* (full pipeline incl. action items → workflow tasks) or *general* (summary/entities/chat only, tasks disabled server-side) — and a multi-provider AI chain (**Gemini → OpenRouter → Ollama**, with a deterministic **Mock engine** for offline/no-key mode) returns a structured analysis: summary, category, key entities, priority with an explanation, suggested action items and observations. Every document is also **chat-able**: a RAG layer chunks the text, embeds it, and answers questions with source citations. The user can convert action items into tracked workflow tasks and monitor everything from a dashboard.

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BROWSER (React 18)                         │
│                                                                     │
│  Pages: Dashboard · Analyzer · Documents · Tasks · Health · Settings│
│  State: AuthContext (JWT) · hooks (useDocuments, useTasks, …)       │
│  API  : axios services → /api/*                                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  HTTP (fetch/axios, Bearer token)
                                │  dev: Vite proxy /api → 127.0.0.1:8001
                                │  docker: Nginx proxy /api → backend:8001
┌───────────────────────────────▼─────────────────────────────────────┐
│                     FASTAPI BACKEND (Python 3.12)                   │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────────┐  │
│  │   Routers     │──▶│   Services   │──▶│   Provider Manager       │  │
│  │ auth/docs/    │   │ auth, doc,   │   │  gemini→openrouter→ollama│  │
│  │ tasks/dash/   │   │ task, dash   │   │  (or mock when MOCK_AI)  │  │
│  │ health/chat   │   │ file, rag    │   └─────────────────────────┘  │
│  └──────┬───────┘   └──────┬───────┘                                │
│         │                  │                                        │
│  ┌──────▼──────────────────▼──────┐   ┌──────────────────────────┐  │
│  │      Pydantic Schemas          │   │  Core: config, security, │  │
│  │  (request/response contract)   │   │  constants, errors       │  │
│  └────────────────────────────────┘   └──────────────────────────┘  │
│                          │                                          │
│                 ┌────────▼────────┐                                 │
│                 │  SQLAlchemy ORM │                                 │
│                 │ User·Document·Task│                               │
│                 └────────┬────────┘                                 │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
              ┌────────────▼─────────────┐
              │ SQLite (local dev)  or   │
              │ PostgreSQL (docker)      │
              └──────────────────────────┘
```

**Key idea:** the browser only ever talks to *one* origin. A proxy (Vite in dev, Nginx in Docker) forwards `/api/*` to FastAPI. That removes CORS problems in development and hides the backend URL in production.

---

## 3. Ports (nothing uses 8000)

| Context | Service | Port | URL |
|---|---|---|---|
| Local dev | FastAPI backend | **8001** | http://127.0.0.1:8001 |
| Local dev | Vite frontend | **5173** | http://localhost:5173 |
| Docker | Nginx frontend | **8080** | http://localhost:8080 |
| Docker | FastAPI backend | 8001 (published) | http://localhost:8001/docs |
| Docker | PostgreSQL | 5432 (internal only) | — |

---

## 4. Directory structure

```
fullstack project/
├── README.md                     ← start here
├── render.yaml                   ← Render.com Blueprint (backend + frontend)
├── docker-compose.yml            ← 3-container stack (db + backend + frontend)
├── .env.example                  ← project-wide env vars for Compose
├── .github/workflows/ci.yml      ← GitHub Actions: pytest + vite build
├── documentation/
│   ├── 01_project_architecture.md        ← this file
│   ├── 02_code_concepts_explained.md
│   ├── 03_docker_cicd.md
│   ├── 04_interview_qa.md
│   ├── 05_verification_checklist.md
│   └── 06_ai_providers.md
│
├── backend/                      ← FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini + alembic/    ← migration scaffolding (optional)
│   ├── pytest.ini
│   └── app/
│       ├── main.py               ← app entry: CORS, routers, error handlers
│       ├── core/
│       │   ├── config.py         ← pydantic-settings (all env vars)
│       │   ├── security.py       ← bcrypt hashing + JWT create/decode
│       │   └── constants.py      ← priorities, statuses, categories
│       ├── database/
│       │   ├── base.py           ← SQLAlchemy DeclarativeBase + utcnow()
│       │   └── connection.py     ← engine, SessionLocal, get_db()
│       ├── models/               ← User, Document, Task, DocumentChunk,
│       │                             ChunkEmbedding tables
│       ├── schemas/              ← Pydantic request/response contracts
│       │                             (incl. chat.py)
│       ├── services/             ← business logic (the "brain")
│       │   ├── auth_service.py
│       │   ├── document_service.py  ← analyze/re-analyze, doc types, RAG sync
│       │   ├── task_service.py
│       │   ├── dashboard_service.py
│       │   ├── chat_service.py   ← grounded Q&A over one document
│       │   ├── file_service.py   ← PDF (pdfplumber→pypdf) / TXT extraction
│       │   ├── ai_service.py     ← single AI entry point (via provider manager)
│       │   ├── rag_service.py    ← chunking, embeddings, grounded answers
│       │   ├── mock_ai.py        ← deterministic local engine (analysis+chat)
│       │   └── ai/               ← multi-provider package
│       │       ├── provider_manager.py   ← ONE fallback layer (retries, notices, metrics)
│       │       ├── gemini_provider.py · openrouter_provider.py
│       │       ├── ollama_provider.py · mock_provider.py
│       │       └── embedding_service.py  ← independent embedding backends
│       ├── routers/              ← HTTP layer (thin!) — incl. chat.py
│       ├── dependencies/         ← get_current_user
│       ├── utils/                ← errors, file validation
│       └── tests/                ← 142 pytest tests (backend/tests/)
│
└── frontend/                     ← React 18 + Vite + Tailwind
    ├── Dockerfile · nginx.conf
    ├── package.json · vite.config.js · tailwind.config.js
    └── src/
        ├── main.jsx · App.jsx · index.css
        ├── routes/AppRoutes.jsx  ← every URL in one place
        ├── pages/                ← Login, Register, Dashboard, Analyzer,
        │                           Documents, Tasks, ApiHealth, Settings, NotFound
        ├── components/
        │   ├── layout/           ← Sidebar, Topbar, AppLayout, ProtectedRoute
        │   ├── common/           ← Modal, Badge, Pagination, Loader, …
        │   ├── auth/ documents/ tasks/ dashboard/
        ├── services/             ← axios clients (api, auth, documents, …)
        ├── hooks/                ← useAuth, useDocuments, useTasks, useDashboard
        ├── context/AuthContext.jsx
        └── utils/                ← constants, formatters, validators
```

**Rule of thumb:** if a file describes *what the app does* → `services/`. If it describes *how it responds to HTTP* → `routers/`. If it describes *what data looks like* → `models/` (storage) or `schemas/` (transport).

---

## 5. Data model

```
┌────────────┐        ┌────────────────────┐        ┌──────────────┐
│   users    │        │     documents      │        │    tasks     │
├────────────┤        ├────────────────────┤        ├──────────────┤
│ id (PK)    │ 1    * │ id (PK)            │ 1    * │ id (PK)      │
│ full_name  │───────▶│ user_id (FK)       │───────▶│ user_id (FK) │
│ email (UQ) │        │ original_filename  │        │ document_id  │──┐
│ hashed_pw  │        │ title              │        │   (FK, NULL) │  │
│ created_at │        │ category           │        │ title        │  │
│ updated_at │        │ extracted_text     │        │ description  │  │
└────────────┘        │ summary            │        │ priority     │  │
                      │ key_entities (JSON)│        │ status       │  │
   1 user             │ priority           │        │ assigned_to  │  │
   N documents        │ priority_reason    │        │ due_date     │  │
   N tasks            │ observations (JSON)│        │ meta (JSON)  │  │
                      │ action_items (JSON)│        │ created_at   │  │
                      │ document_type      │        │ updated_at   │  │
                      │ processing_status  │        └──────────────┘  │
                      │ user_notes         │                          │
                      │ created_at/updated │                          │
                      └────────────────────┘                          │
                                     ▲                                │
                                     └────────────────────────────────┘
                              tasks.document_id is NULLABLE
                              (SET NULL when the document is deleted)

  RAG side-tables (one-to-many, CASCADE with the document):
  ┌──────────────────┐   ┌────────────────────┐
  │ document_chunks  │──▶│ chunk_embeddings   │
  │ id, document_id  │   │ chunk_id (FK)      │
  │ chunk_index,     │   │ provider, model,   │
  │ content,         │   │ dimension,         │
  │ content_hash     │   │ vector (JSON)      │
  └──────────────────┘   └────────────────────┘
```

### Relationships

| Relationship | Type | On delete |
|---|---|---|
| User → Documents | one-to-many | `CASCADE` (user removed ⇒ documents removed) |
| User → Tasks | one-to-many | `CASCADE` |
| Document → Tasks | one-to-many (optional) | `SET NULL` — **tasks survive** a document deletion |
| Document → `document_chunks` | one-to-many | `CASCADE` (RAG chunks die with their document) |
| `document_chunks` → `chunk_embeddings` | one-to-one | `CASCADE` |

### RAG tables (`document_chunks` + `chunk_embeddings`)

Long documents are split into overlapping chunks for retrieval-augmented
chat. Each chunk stores a SHA-256 **content hash** (unchanged chunks are
never re-embedded) and its embedding row records **`provider`, `model`,
`dimension`** next to the JSON vector — vectors from different models live
in incompatible spaces, so a model change triggers a clean re-embed instead
of silently mixing them. Vectors are plain JSON columns: they work on both
SQLite (dev) and PostgreSQL (Docker) with no extension.

### Document types (`documents.document_type`)

`task` | `general` (default `task`) is a real column, not UI state. For
`general` documents the service layer forces `action_items=[]` on
analyze/re-analyze, so workflow tasks can never be created — even via a
direct API call. `task` documents keep the full pipeline. Chat works for
both types.

### JSON columns (and why)

`key_entities`, `action_items`, `observations` and `meta` are stored as JSON because their shape is *produced by the AI* and validated by Pydantic before storage. They are read as whole values — never filtered or joined on — so a JSON column is simpler than four extra tables. (In a bigger product you might normalise `action_items` into their own table.)

### Ownership is a column, not a session

Every table carries `user_id`, and **every query filters on it**. That single line is what stops user B from reading user A's document by guessing an id — they receive `404`, so the resource's existence is not even revealed.

---

## 6. Request lifecycle (the most important diagram)

Take the flagship action: **analyze a document**.

```
Browser                      FastAPI                        AI engine
   │                            │                              │
   │ 1. POST /api/documents/analyze (multipart)                │
   │    file=report.pdf  OR  text="..."                        │
   │    Authorization: Bearer <jwt>                            │
   ├───────────────────────────▶│                              │
   │                            │ 2. get_current_user          │
   │                            │    decode JWT → user_id      │
   │                            │    → 401 if invalid          │
   │                            │                              │
   │                            │ 3. file_service              │
   │                            │    extension + size +        │
   │                            │    %PDF signature checks     │
   │                            │    extract text              │
   │                            │    (pdfplumber → pypdf)      │
   │                            │    + document_type field     │
   │                            │                              │
   │                            │ 4. ai_service.analyze_text   │
   │                            ├─────────────────────────────▶│
   │                            │                              │ 5. provider chain:
   │                            │                              │    gemini → openrouter
   │                            │                              │    → ollama (or mock)
   │                            │◀─────────────────────────────┤
   │                            │ 6. Pydantic validation       │
   │                            │    AIAnalysis (strict)       │
   │                            │    → 502 if the model lies   │
   │                            │                              │
   │                            │ 7. document_service          │
   │                            │    doc_type=general ⇒        │
   │                            │    action_items=[]           │
   │                            │    INSERT + commit           │
   │                            │    (+ best-effort RAG sync)  │
   │                            │                              │
   │ 8. 201 Created            │                              │
   │    { message, ai_provider, │                              │
   │      ai_provider_notice,   │                              │
   │      document: {...} }     │                              │
   │◀───────────────────────────┤                              │
   │                            │                              │
   │ 9. React renders sections A–F + provider badge           │
```

**Why one endpoint for both file and text?** The `analyze` endpoint always receives `multipart/form-data` with either a `file` **or** a `text` field — one code path, one test matrix, one thing to explain. Passing `document_id` switches it to *re-analyze in place* (updates the existing row instead of creating a duplicate).

The optional `document_type` form field (`task` default, or `general`)
travels the same way and is validated — anything else gets a 400.

**Chat is a sibling endpoint:** `POST /api/documents/{id}/chat` loads the
*stored* `extracted_text` of that one document (ownership-checked → 404
for other users), optionally retrieves the most relevant chunks via
embeddings (RAG), and returns `{ answer, provider, sources[] }`. The same
provider chain answers; the Mock engine answers extractively so it can
never hallucinate.

---

## 7. The AI layer (multi-provider with automatic fallback)

```
      ai_service.analyze_text(text)   /   chat_service.answer_question()
                            │
                            ▼
          services/ai/provider_manager.py        ← the ONE fallback layer
          ┌───────────────────────────────────────────────────────┐
          │ chain = MOCK_AI ? [mock]                              │
          │        : AI_PROVIDER_PRIORITY → gemini, openrouter,   │
          │                                ollama (configured     │
          │                                ones only)            │
          │ for each provider:  retry × AI_MAX_RETRIES (backoff)  │
          │   transient error (429/quota/5xx/conn/timeout/auth/   │
          │   bad model output) → next provider                   │
          │   invalid input     → raise 400 immediately           │
          │ log every request → execution_log (metrics + notices) │
          └───────────────────────────────────────────────────────┘
                            │
                            ▼
     gemini_provider · openrouter_provider · ollama_provider · mock_provider
                            │
                            ▼
     validate_analysis() → AIAnalysis (Pydantic, inside the manager call)
                            │
        ┌───────────────────┴───────────────────┐
        │  valid                               │ invalid
        ▼                                       ▼
   store in documents table          AppError 400/502/503/504
   (+ ai_provider, ai_provider_notice)
```

Design rules:

1. **One contract.** Every provider returns the same JSON shape; Pydantic (`schemas/ai.py`) is the gatekeeper, and validation runs *inside* the manager call so a malformed reply falls back to the next provider instead of failing the request. A hallucinated priority like `"urgent"` is normalised to `High`; an unknown category falls back to `General Document`.
2. **Honest labelling.** The API returns `ai_provider: "mock" | "gemini" | "openrouter" | "ollama"` with every analysis, plus `ai_provider_notice` when fallback really happened. The UI shows a visible badge for whichever provider answered. Mock output is never presented as real AI output.
3. **Failure is typed.** Timeouts → 504, rate limits/quota/provider down → 503, malformed model output → 502, invalid input → 400 (never falls back). The frontend shows the readable `detail` message.
4. **Adding a provider** = one new `services/ai/<name>_provider.py` implementing `AIProvider` + one line in `build_provider_chain()`. Routers, models and React never change. See `documentation/06_ai_providers.md`.

### What the Mock engine actually does

It is a **real feature, not a stub**: keyword scoring picks the category, regexes extract emails/dates/money/phones/URLs/organizations/reference numbers, urgency phrasing drives priority, and sentences containing action verbs become suggested action items with dates only when a date is literally present. Output is deterministic, which is exactly what you want for demos, CI and interviews.

---

## 8. Authentication & security model

| Concern | Implementation |
|---|---|
| Password storage | bcrypt, 12 rounds, explicit 72-byte truncation, per-password salt |
| Password transport | HTTPS in production; JSON body over the proxy |
| Session | JWT (HS256) with `sub` = user id, `exp`, `iat`; 24h default |
| Token transport | `Authorization: Bearer <token>` header |
| Token storage (frontend) | `localStorage` — documented trade-off (see doc 02) |
| Expired/invalid token | backend 401 → axios interceptor clears token → redirect `/login` |
| Route protection | `ProtectedRoute` waits for session restore, then redirects |
| Data isolation | `user_id` filter in every service query; 404 (not 403) on mismatch |
| Upload safety | extension allow-list + size limit + real `%PDF` magic-byte check |
| Error safety | global handler never leaks stack traces; health endpoints never leak keys |
| CORS | explicit origin allow-list from `CORS_ORIGINS` env var |

**Why 404 instead of 403 for another user's resource?** Returning 403 confirms *"this id exists but is not yours"* — an attacker can enumerate ids. 404 says *"nothing here"*, revealing nothing.

---

## 9. Error handling strategy

```
Service raises AppError(detail, status_code)
        │
        ▼
main.py exception handler → JSONResponse { "detail": "..." }
        │
        ▼
axios interceptor → getErrorMessage(error) → toast / inline banner
```

Three layers:

1. **`AppError`** (our own) — friendly, safe messages with precise status codes (400/401/404/409/502/503/504).
2. **`RequestValidationError`** — Pydantic's 422 is reformatted into readable `field: message` text.
3. **Catch-all `Exception`** — logs the traceback server-side, returns only `"An unexpected server error occurred."` to the client.

The frontend has a single `getErrorMessage()` helper, so every failure — network down, 401, validation — produces a human sentence. The network-failure message even tells the developer the backend port: *"Cannot reach the server. Is the backend running on port 8001?"*

---

## 10. Frontend architecture

```
App.jsx
 └─ AuthProvider            ← restores session, exposes signIn/signUp/signOut
     └─ BrowserRouter
         └─ AppRoutes       ← ALL routes declared here (one file, easy to scan)
              ├─ /login /register        → PublicOnly (redirect if authed)
              └─ ProtectedRoute           → AppLayout (Sidebar + Topbar)
                   └─ /dashboard /analyzer /documents /tasks /health /settings
```

**State strategy — deliberately simple:**

| Need | Solution |
|---|---|
| Current user | `AuthContext` (React context) |
| Server data (lists) | custom hooks: `useDocuments`, `useTasks`, `useDashboard` |
| Form state | local `useState` per page/modal |
| Server mutations | direct service calls + `toast` + `refresh()` |

No Redux, no React Query — for this size, hooks with `useCallback`/`useEffect` are easier to read and have zero boilerplate. Every hook follows the same shape: `{ filters, updateFilters, goToPage, refresh, items, loading, error }`, so Documents and Tasks behave identically.

**Why services/ instead of fetch in components?** `services/api.js` is the *only* file that knows the backend URL, attaches the token, applies the timeout, and converts errors to messages. Adding an endpoint = add one 3-line function in the right service file.

---

## 11. Environment & configuration

One principle: **no secret, port or key is written in business code.**

- Backend: `app/core/config.py` (pydantic-settings) reads `backend/.env` + process env. Everything else imports `settings`.
- Frontend: `import.meta.env.VITE_API_URL` — empty in dev means *"use the Vite proxy"* (no CORS).
- Docker Compose: injects env vars into containers, including the PostgreSQL URL.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./docuflow.db` | Compose/Render override with PostgreSQL |
| `MOCK_AI` | `true` | `true` = deterministic offline engine; `false` = provider chain |
| `AI_PROVIDER_PRIORITY` | `gemini,openrouter,ollama` | order of real providers tried |
| `AI_FALLBACK_ENABLED` / `AI_MAX_RETRIES` | `true` / `2` | per-provider retry + failover |
| `SECRET_KEY` | dev value | **change before deploying** |
| `CORS_ORIGINS` | localhost:5173/8080 | comma-separated allow-list |
| `VITE_API_URL` | *(empty)* | empty = proxy in dev; API URL in prod builds |

---

## 12. Testing strategy

| Layer | Tool | Count | What it proves |
|---|---|---|---|
| API end-to-end | pytest + TestClient | **142** | every endpoint, status code, isolation rule, document types, chat, provider fallback |
| AI engine | pytest | (included above) | mock output always satisfies the strict schema; provider-chain error taxonomy |
| Live server | manual smoke script | — | real HTTP against uvicorn on 8001 |
| Frontend | `vite build` in CI | — | the app compiles for production |

Test isolation is handled in `conftest.py`: it points the app at a temporary SQLite file and sets `MOCK_AI=true` **before** the app is imported, empties all tables around each test, and zeroes the mock delay so the suite runs fast. Tests assert *behaviour* (404 not 403, hash never in responses, duplicate task rejected) rather than implementation details.

---

## 13. Design decisions & trade-offs (interview-ready)

1. **SQLite in dev, PostgreSQL in Docker** — zero-install onboarding locally; production-grade in Compose. One `DATABASE_URL` switches them.
2. **`Base.metadata.create_all()` at startup + Alembic scaffolding** — beginners can run the app with one command; migrations are ready when the schema starts evolving.
3. **localStorage JWT instead of httpOnly cookie** — simpler to explain and debug; the XSS trade-off is documented rather than hidden.
4. **Mock AI is deterministic** — a fake that returns random data would break tests and mislead users; rules + regex give reproducible, honest results.
5. **`SET NULL` on document delete** — deleting a report should not silently destroy the work it created.
6. **404 for cross-user access** — prevents id enumeration.
7. **Sequential task creation from action items** — keeps duplicate detection predictable and avoids hammering the API with parallel writes.
8. **`passlib` dropped for direct `bcrypt`** — passlib 1.7.4 is unmaintained and crashes with bcrypt ≥ 4.1; calling the maintained library directly is simpler and safer.
9. **Document type is a persisted column enforced in the service layer** — `general` documents can never produce action items, even via direct API calls; chat still works for both types.
10. **`pdfplumber` primary + `pypdf` fallback for PDFs** — layout-aware extraction preserves table rows/columns far better; pypdf covers files pdfplumber cannot parse. Neither does OCR (scanned PDFs honestly report "no readable text").
11. **Embeddings are provider-independent** — generation and embedding chains are configured separately, vectors record `provider`/`model`/`dimension`, and a model change triggers re-embedding instead of mixing incompatible vector spaces.
12. **Render Blueprint (`render.yaml`)** — one file deploys backend + static frontend; secrets stay `sync: false` so they are entered in the dashboard, never committed.

---

## 14. Performance & scalability notes

- **Indexing:** `users.email` (unique), and `user_id`/`created_at`/`priority`/`status` on documents and tasks — every list query filters by `user_id` first.
- **Pagination is server-side** (10–100 rows/page) — the browser never receives the whole table.
- **Counts are computed in Python from one query** — fine at this scale; at millions of rows you would move to `GROUP BY` aggregates.
- **AI calls run in a worker thread with a hard timeout** — a slow provider can never block the event loop or leak threads (single-use pool).
- **`pool_pre_ping=True`** — survives database restarts gracefully (important for PostgreSQL).
- **Gzip + immutable asset caching** in Nginx; hashed filenames make 30-day caching safe.

**Next steps if this went to real production:** Alembic migrations for every change, Redis-backed rate limiting, S3 for file storage, background jobs (Celery) for analysis, httpOnly cookies with CSRF, structured logging + Sentry, and horizontal backend workers behind a load balancer.

---

*Continue with [02 — Code Concepts Explained](02_code_concepts_explained.md).*
