# DocuFlow AI

**Turn Documents into Decisions** — a complete, beginner-friendly, production-quality full-stack AI document intelligence SaaS.

Upload a PDF or paste text → an AI engine returns a **summary, category, key entities, priority with an explanation, action items and observations** → convert those action items into **tracked workflow tasks** → watch everything on a **live dashboard**.

- ⚛️ **Frontend:** React 18 · Vite · Tailwind CSS · Recharts · Framer Motion
- ⚡ **Backend:** FastAPI · SQLAlchemy 2.0 · Pydantic v2 · JWT auth
- 🤖 **AI:** **multi-provider chain — Gemini → OpenRouter → Ollama** with automatic fallback on rate limits/outages · **Mock engine by default** (no API key, no cost) · independent embeddings + RAG · the UI always shows which provider answered
- 🐳 **Docker Compose** (PostgreSQL) · **GitHub Actions CI** (138 tests + build)
- 📚 **4 documentation files** written for beginners and interview prep

> **Ports:** backend **8001** · frontend dev **5173** · Docker **8080**. *(Nothing uses port 8000.)*

---

## Quick start (local development — 2 minutes)

### Prerequisites

| Tool | Version used | Check |
|---|---|---|
| Python | 3.12+ | `python --version` |
| Node.js | 20+ (22 used) | `node --version` |

### 1. Backend → http://127.0.0.1:8001

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt

# run (creates backend/docuflow.db automatically on first start)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 2. Frontend → http://localhost:5173

```bash
cd frontend
npm install
npm run dev
```

### 3. Open http://localhost:5173 and register an account

You're in. Mock AI is active by default — **no API key needed**.

### 4. Run the tests

```bash
cd backend
pytest --tb=short -q      # 138 tests, well under a minute
```

---

## Quick start (Docker — production-like)

```bash
cp .env.example .env      # then set a real SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

| Service | URL |
|---|---|
| App | **http://localhost:8080** |
| API docs (Swagger) | http://localhost:8001/docs |
| PostgreSQL | internal only (not published) |

```bash
docker compose down        # stop, keep data
docker compose down -v     # stop, delete database
docker compose logs -f backend
```

---

## Deploy to Render (free tier, ~15 minutes)

The repo includes a **`render.yaml` Blueprint** — Render reads it and creates both services automatically.

1. **Push the repo to GitHub** (`git init` → commit → push to a new repo).
2. **Get a free Postgres database** — Render's filesystem is ephemeral so SQLite data would be lost. Use [Neon](https://neon.tech) or [Supabase](https://supabase.com) (free, no card). Copy the connection string and change `postgresql://` to `postgresql+psycopg2://` (add `?sslmode=require` if needed).
3. **Render dashboard → New → Blueprint** → select the repo → Apply.
4. When prompted, fill the `sync: false` secrets:
   - `DATABASE_URL` — your Postgres string from step 2
   - `SECRET_KEY` — auto-generated, or any long random string
   - `GEMINI_API_KEY` / `OPENROUTER_API_KEY` — optional; set `MOCK_AI=true` to run with zero keys
   - `CORS_ORIGINS` — `https://docuflow-frontend.onrender.com` (use your actual frontend URL)
5. Wait for both services to deploy (~5–10 min first build), then copy the backend URL into the frontend's `VITE_API_URL` env var and redeploy the frontend.
6. Open `https://docuflow-frontend.onrender.com` and register.

> **Free-tier reality:** services sleep after ~15 min idle — the first request takes ~30–60s (cold start). Health checks use `/api/health`, so Render keeps the backend honest automatically.

---

## Ports at a glance

| Context | Service | Port |
|---|---|---|
| Local dev | FastAPI backend | **8001** |
| Local dev | Vite dev server | **5173** |
| Docker | Nginx (React + API proxy) | **8080** |
| Docker | FastAPI backend | 8001 (published for `/docs`) |
| Docker | PostgreSQL | 5432 (internal only) |

---

## Project structure

```
fullstack project/
├── README.md                     ← you are here
├── docker-compose.yml            ← db + backend + frontend
├── .env.example                  ← env vars for Compose
├── .github/workflows/ci.yml      ← GitHub Actions: pytest + build
│
├── documentation/
│   ├── 01_project_architecture.md      ← how the system fits together
│   ├── 02_code_concepts_explained.md   ← every concept tied to real code
│   ├── 03_docker_cicd.md               ← Docker + pipeline explained
│   ├── 04_interview_qa.md              ← 48 Q&A
│   ├── 05_verification_checklist.md    ← what was executed and verified
│   └── 06_ai_providers.md              ← provider setup, fallback, RAG, testing
│
├── backend/                      ← FastAPI app
│   ├── Dockerfile · requirements.txt · pytest.ini
│   ├── alembic.ini + alembic/    ← migration scaffolding
│   └── app/
│       ├── main.py               ← entry: CORS, routers, error handlers
│       ├── core/                 ← config, security (bcrypt + JWT), constants
│       ├── database/             ← engine, SessionLocal, get_db()
│       ├── models/               ← User, Document, Task (+ RAG chunk tables)
│       ├── schemas/              ← Pydantic contracts (incl. strict AI schema)
│       ├── services/             ← the business logic "brain"
│       │   ├── auth_service.py · document_service.py · task_service.py
│       │   ├── dashboard_service.py · file_service.py
│       │   ├── ai_service.py     ← single AI entry point (via provider manager)
│       │   ├── rag_service.py    ← chunking, embeddings, grounded answers
│       │   ├── mock_ai.py        ← deterministic engine (default)
│       │   └── ai/               ← multi-provider package
│       │       ├── provider_manager.py   ← selection, retries, fallback, metrics
│       │       ├── gemini_provider.py · openrouter_provider.py
│       │       ├── ollama_provider.py · mock_provider.py
│       │       └── embedding_service.py  ← independent embedding backends
│       ├── routers/              ← thin HTTP layer
│       ├── dependencies/         ← get_current_user
│       └── utils/                ← errors, file validation
│   │
│   └── tests/                    ← 138 pytest tests (all network faked)
│
└── frontend/                     ← React app
    ├── Dockerfile · nginx.conf
    └── src/
        ├── routes/AppRoutes.jsx  ← every URL in one file
        ├── pages/                ← Login, Register, Dashboard, Analyzer,
        │                           Documents, Tasks, ApiHealth, Settings, NotFound
        ├── components/           ← layout/ common/ auth/ documents/ tasks/ dashboard/
        ├── services/             ← axios clients (the only files knowing the URL)
        ├── hooks/                ← useAuth, useDocuments, useTasks, useDashboard
        ├── context/AuthContext.jsx
        └── utils/                ← constants, formatters, validators
```

**Where do I change X?**

| I want to… | File |
|---|---|
| add a backend endpoint | `backend/app/routers/<area>.py` + `services/<area>_service.py` |
| change a table | `backend/app/models/*.py` |
| change what the AI returns | `backend/app/schemas/ai.py` |
| add an AI provider | new `services/ai/<name>_provider.py` (implements `AIProvider`) + one line in `provider_manager.build_provider_chain()` |
| add a frontend page | `src/pages/X.jsx` + one line in `src/routes/AppRoutes.jsx` |
| add an API call | `src/services/<area>.js` |
| change a shared UI rule | `src/index.css` (`@layer components`) |
| change statuses/priorities | `app/core/constants.py` **and** `src/utils/constants.js` |

---

## Features — everything works

### Auth
- Register / login / logout with bcrypt-hashed passwords (12 rounds)
- JWT sessions (HS256, 24h) with automatic logout on 401
- Protected and public-only routes; deep links return you where you were going

### Analyzer
- **PDF upload** (magic-byte validation + layout-aware **pdfplumber** extraction with pypdf fallback — table-heavy PDFs stay readable) or **pasted text**
- Choose a **document type** before analyzing:
  - **Task / work document** → full pipeline: summary, entities, priority, action items → workflow tasks
  - **General document** → analysis + chat only; action items and task creation are disabled server-side
- Sections **A–F**: Summary · Key Entities · Category · Priority + explanation · Action Items · Observations
- Re-analyze in place, edit details, save notes, delete — all from the results panel
- One click converts selected action items into tasks (duplicates rejected by the backend)

### Chat with documents
- Ask questions about any uploaded document — the AI answers using only that document's extracted text
- Long documents use **RAG**: the top matching chunks are retrieved and the answer shows **source chips** (`chunk N · score`) — only chunks that were really used, never invented citations
- Available in the Document Analyzer results and inside the document detail drawer
- Works with every configured provider; mock answers are labelled as simulated, and a fallback notice appears when another provider had to answer
- Ownership enforced server-side — you can never chat with another user's document

### Documents
- Server-side search, category / priority / status filters, 4 sort orders, pagination
- Detail drawer with full analysis, linked tasks, original text, and notes (persisted)
- Edit and delete with confirmation — tasks are **kept** when their document is deleted

### Tasks
- **List view** (paginated table) and **Board view** (Pending / In Review / Completed)
- Create, edit, delete, and move between stages; priority, assignee, due date
- Live status counts come from the backend, so tabs always reflect real data

### Dashboard
- KPIs, activity chart, task-status and priority distributions, recent documents/tasks
- **Every number comes from the API** — nothing is hardcoded

### API Health & Settings
- Live API + database + AI status, refreshed every 30 seconds
- **Provider chain cards** (Gemini / OpenRouter / Ollama / Mock): configured, reachable, model, detail
- **Real metrics**: requests, successes, failures, average response time, fallback events + the recent-fallback list
- Embedding backend (provider · model · dimensions), priority and fallback setting
- Profile, active AI mode, honest security notes, sign out

### Which AI answered? — always visible
The top bar shows a permanent badge for the **active provider** (🧪 Mock AI / Gemini / OpenRouter / Ollama), every analysis carries `ai_provider` from the API, and when automatic fallback happened a notice is shown, e.g. *"Google Gemini quota was exhausted. OpenRouter was used for this request."* Mock output is never presented as real AI output.

```bash
# backend/.env
MOCK_AI=true                       # deterministic local engine — no key needed (default)

# real providers (any subset — the chain skips what isn't configured)
MOCK_AI=false
AI_PROVIDER_PRIORITY=gemini,openrouter,ollama
GEMINI_API_KEY=your-key-here       # primary
OPENROUTER_API_KEY=your-key-here   # fallback (free models only by default)
OLLAMA_ENABLED=true                # optional local fallback: also needs OLLAMA_MODEL
```

Full setup per provider (free-only guard, spend cap, Ollama install, embeddings):
[`documentation/06_ai_providers.md`](documentation/06_ai_providers.md)

---

## API reference

Base URL: `http://127.0.0.1:8001` · Interactive docs: `/docs` · All routes below are under `/api`

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | — | API + database status, uptime |
| GET | `/health/ai` | — | provider chain + availability, embeddings, metrics (never the key) |
| POST | `/auth/register` | — | create account → JWT |
| POST | `/auth/login` | — | sign in → JWT |
| GET | `/auth/me` | ✔ | current user profile |
| POST | `/documents/analyze` | ✔ | **multipart**: `file` *or* `text` (+ optional `document_id` to re-analyze) |
| GET | `/documents` | ✔ | list + search/filter/sort/paginate |
| GET | `/documents/{id}` | ✔ | full analysis + linked tasks |
| PUT | `/documents/{id}` | ✔ | update title / category / priority / notes |
| DELETE | `/documents/{id}` | ✔ | delete (tasks survive via `SET NULL`) |
| GET | `/tasks` | ✔ | list + counts + filters |
| POST | `/tasks` | ✔ | create (from UI or AI action item) |
| PUT | `/tasks/{id}` | ✔ | update (incl. status transitions) |
| DELETE | `/tasks/{id}` | ✔ | delete |
| GET | `/dashboard/stats` | ✔ | KPI cards |
| GET | `/dashboard/analytics` | ✔ | chart data |
| GET | `/documents/search?q=` | ✔ | quick global search |

Cross-user access returns **404** (never 403), so ids can't be enumerated.

---

## Testing

```bash
cd backend
pytest --tb=short -q        # 138 tests
```

What they prove — *behaviour, not implementation*:

- ✅ another user's document returns **404, not 403**
- ✅ `hashed_password` **never** appears in any response
- ✅ a fake `.pdf` (renamed file) is **rejected** by magic-byte checks
- ✅ a duplicate task is rejected
- ✅ malformed AI output → **502**, nothing stored
- ✅ Mock AI output always satisfies the strict Pydantic schema
- ✅ fallback happens **only** for transient errors — invalid input never falls back
- ✅ OpenRouter free-only mode never requests a paid model
- ✅ unchanged document chunks are **re-embedded never** (hash reuse); a model change re-embeds cleanly
- ✅ RAG retrieval is user-scoped and cites only chunks that were really retrieved
- ✅ all provider/network boundaries are **faked** — the suite makes zero paid API calls

Frontend verification: `npm run build` runs in CI on every push.

---

## Documentation

| # | File | What's inside |
|---|---|---|
| 1 | [`documentation/01_project_architecture.md`](documentation/01_project_architecture.md) | overview, diagrams, data model, request lifecycle, trade-offs |
| 2 | [`documentation/02_code_concepts_explained.md`](documentation/02_code_concepts_explained.md) | 24 concepts, each tied to the file where it lives |
| 3 | [`documentation/03_docker_cicd.md`](documentation/03_docker_cicd.md) | Docker Compose, Nginx, GitHub Actions, troubleshooting |
| 4 | [`documentation/04_interview_qa.md`](documentation/04_interview_qa.md) | **48 interview Q&A** + quick-fire round |

---

## Design decisions (the short version)

1. **Proxy, not CORS** — Vite and Nginx forward `/api`, so the browser sees one origin and the backend URL never ships to the client.
2. **SQLite locally, PostgreSQL in Docker** — zero-install onboarding; one `DATABASE_URL` switches them.
3. **Mock AI is deterministic** — a fake returning random data would break tests and mislead users.
4. **`SET NULL` on document delete** — deleting a report must not destroy the work it created.
5. **404 for cross-user access** — prevents id enumeration.
6. **Direct `bcrypt` instead of `passlib`** — passlib 1.7.4 crashes with bcrypt ≥ 4.1.
7. **`localStorage` JWT** — simple and debuggable; the XSS trade-off is documented, not hidden.
8. **`create_all()` + Alembic scaffolding** — beginners run one command; migrations are ready when the schema evolves.

---

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./docuflow.db` | Compose overrides with PostgreSQL |
| `SECRET_KEY` | dev value | **change before deploying** |
| `MOCK_AI` | `true` | `false` requires `GEMINI_API_KEY` |
| `GEMINI_API_KEY` | — | only needed for real AI |
| `GEMINI_MODEL` | `gemini-1.5-flash` | model name |
| `CORS_ORIGINS` | localhost:5173, 8080 | comma-separated allow-list |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime |
| `MAX_FILE_SIZE_MB` | `10` | upload limit |
| `VITE_API_URL` | *(empty)* | empty = use the dev proxy |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Cannot reach the server" | backend not running on **8001** — start it with `python -m uvicorn app.main:app --port 8001` |
| Port already in use | the app uses 8001 / 5173 / 8080 — **never 8000** |
| `bcrypt` / `passlib` error | this project uses `bcrypt` directly; run `pip install -r requirements.txt` |
| Blank page in dev | restart Vite: `npm run dev` |
| Tests hitting your real DB | don't — `conftest.py` sets a temp DB *before* importing the app |
| Docker: backend restarts | `docker compose up -d db` first, then `docker compose up -d` |
| Reset local data | stop the backend and delete `backend/docuflow.db` |

---

## License

MIT — free to use, modify and learn from.
