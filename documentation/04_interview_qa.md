# DocuFlow AI — Interview Q&A

> **Document 4 of 6** · [Architecture](01_project_architecture.md) · [Code Concepts](02_code_concepts_explained.md) · [Docker & CI/CD](03_docker_cicd.md) · [Checklist](05_verification_checklist.md) · [AI Providers](06_ai_providers.md)

**73 questions** grouped by topic, each with a *short answer* (say this out loud) and a *deeper note* (only if they ask). Every answer points at real code in this repository.

**How to use this file:** answer in this order — *what it is → why we used it → what the trade-off is*. The trade-off is what separates a junior answer from a mid-level one.

---

## Table of contents

1. [Project & architecture](#part-1--project--architecture-17)
2. [Backend / FastAPI](#part-2--backend--fastapi-10)
3. [Database & SQLAlchemy](#part-3--database--sqlalchemy-7)
4. [Authentication & security](#part-4--authentication--security-7)
5. [AI integration](#part-5--ai-integration-5)
6. [Frontend / React](#part-6--frontend--react-7)
7. [Testing, Docker & CI](#part-7--testing-docker--ci-6)
8. [Tricky behavioural questions](#part-8--tricky-behavioural--scenario-questions)
9. [Document types, chat & deployment](#part-9--document-types-chat--deployment-5)

---

# Part 1 — Project & architecture (17)

### 1. Give me a 60-second overview of this project.

**Short answer:**
"DocuFlow AI is a full-stack SaaS that turns documents into decisions. A user signs up, uploads a PDF or pastes text, picks a document type — task/work gets the full pipeline including action items that become tracked workflow tasks, general documents get analysis plus chat only — and a multi-provider AI chain (Gemini → OpenRouter → Ollama, with a deterministic Mock engine for offline mode) returns a structured analysis: summary, category, entities, priority, action items. Every document is also chat-able via a RAG layer with source citations, and a dashboard shows real metrics from the database."

**Deeper:** React 18 + Vite + Tailwind front end, FastAPI + SQLAlchemy backend, JWT auth, 142 pytest tests, pdfplumber PDF extraction, Docker Compose with PostgreSQL, GitHub Actions CI, and a Render Blueprint for one-click deployment.

---

### 2. Why did you choose FastAPI over Flask or Django?

**Short answer:**
"FastAPI gives me three things Flask doesn't out of the box: request validation and JSON contracts through Pydantic, automatic OpenAPI docs at `/docs`, and native async. I picked it over Django because Django's ORM and admin are heavier than this project needs — I'd be fighting the framework instead of using it."

**Deeper:** the `response_model=` on each route is also response filtering for free — `UserOut` can simply omit `hashed_password` and the leak is impossible by construction.

---

### 3. Walk me through the architecture.

**Short answer:**
"Three layers on each side. On the backend: routers handle HTTP, services hold business rules, models define storage — with Pydantic schemas as the contract between the outside world and the code. On the frontend: pages hold UI, hooks hold stateful logic, services are the only files that know the backend URL. The browser talks to one origin; a proxy forwards `/api` to FastAPI."

**Deeper:** see `documentation/01`, §2 and §4. The one-line rule: *services = what the app does, routers = how it responds to HTTP, models = what data looks like stored, schemas = what data looks like in transit.*

---

### 4. Why is there a proxy instead of calling the backend directly?

**Short answer:**
"Two reasons. In development, `localhost:5173` calling `127.0.0.1:8001` is a cross-origin request, so every call would need CORS and preflight. With the Vite proxy the browser only ever sees one origin. In production Nginx does exactly the same job, which also means the backend URL never ships to the browser and there's zero CORS configuration to get wrong."

**Deeper:** `vite.config.js` proxies `/api` → `127.0.0.1:8001`; `frontend/nginx.conf` proxies `/api/` → `backend:8001`. `VITE_API_URL` empty in dev means "use the proxy."

---

### 5. What's the request lifecycle of "Analyze a document"?

**Short answer:**
"The browser posts multipart form data with a file or text. `get_current_user` decodes the JWT. `file_service` validates extension, size and the `%PDF` magic bytes, then extracts text with pypdf. `ai_service.analyze_text` runs the provider inside a worker thread with a 30-second timeout, and the result is validated by a strict Pydantic schema. If valid, `document_service` inserts the row and returns 201 with `ai_provider` so the UI can label it. React renders sections A–F."

**Deeper:** if `document_id` is present the same endpoint updates the existing row instead of creating a duplicate (re-analysis in place).

---

### 6. Why one endpoint for both file upload and pasted text?

**Short answer:**
"One code path. Both arrive as `multipart/form-data` — either a `file` field or a `text` field — so validation, error handling and tests are written once instead of twice. It also makes the API easy to explain: one route, two inputs."

**Trade-off:** slightly less RESTful than two dedicated endpoints, but far less duplication for a beginner-readable codebase.

---

### 7. What is stateless architecture, and did you use it?

**Short answer:**
"Stateless means the server stores no per-user session — every request carries everything needed to identify the user. I use JWTs, so any backend instance can serve any request without shared memory. That's what makes horizontal scaling possible later."

**Deeper:** the trade-off is that a stateless token can't be revoked before it expires. Mitigations are a short TTL or a denylist; I document the localStorage choice in `documentation/02`.

---

### 8. How do you handle errors?

**Short answer:**
"Three layers. Services raise `AppError(detail, status_code)` for known failures — the global handler turns it into `{"detail": "..."}`. Pydantic's 422 gets reformatted into readable `field: message` text. A catch-all logs the traceback server-side and returns only a generic message, so stack traces never reach the client. On the frontend, one `getErrorMessage()` helper turns any failure into a human sentence."

**Deeper:** status codes are chosen deliberately — 409 duplicate email, 404 cross-user access, 502 bad AI output, 503 missing API key, 504 AI timeout.

---

### 9. How do the frontend and backend stay in sync on data shapes?

**Short answer:**
"The Pydantic response schemas are the single source of truth on the server, and the frontend services just consume that JSON. Where a value is an enum — priorities, statuses, categories — I keep a constants file on each side and they're documented as needing to stay in sync."

**Deeper:** `app/core/constants.py` ↔ `src/utils/constants.js`. The "where do I change X" table in `documentation/02` calls this out explicitly.

---

### 10. What would you change if this went to production tomorrow?

**Short answer:**
"Five things, in order: real Alembic migrations for every schema change, httpOnly cookies with CSRF instead of localStorage, file storage in S3 rather than local disk, background jobs so analysis doesn't block a request, and structured logging with error tracking."

**Deeper:** then Redis rate limiting, TLS at the proxy, and multiple backend workers behind a load balancer. Listing *ordered* priorities matters more than the list itself.

---

### 11. Why is nothing hardcoded — ports, keys, URLs?

**Short answer:**
"Because the same code has to run in three places: my machine, Docker, and CI. One `Settings` object built by pydantic-settings reads `.env` and process variables, and everything else imports `settings`. There's exactly one place to look when a value is wrong."

**Deeper:** ports 8001/5173/8080 come from config — the app never references a port literal. `MOCK_AI` is a typed `bool`, so the string `"false"` parses as `False` rather than truthy.

---

### 12. What's the trade-off of using SQLite locally and PostgreSQL in Docker?

**Short answer:**
"Zero-install onboarding — a beginner runs one command and a database exists. Docker gives a production-grade database for demos and CI. One `DATABASE_URL` switches them, so no code changes."

**Deeper:** the risk is dialect drift (e.g. `JSON` behaves differently). Mitigation: keep to portable types, run the same test suite in both, and `pool_pre_ping=True` for PostgreSQL restarts.

---

### 13. How is this multi-tenant?

**Short answer:**
"Row-level isolation. Every table carries `user_id` and every query filters on it, so user B simply can't see user A's rows. Cross-user access returns 404 rather than 403."

**Why 404:** "403 tells an attacker *this id exists but isn't yours*, which lets them enumerate ids. 404 says *nothing here* and reveals nothing."

**Deeper:** a real multi-tenant product would add a database-level guarantee (Postgres RLS) on top of the application filter.

---

### 14. How do you keep secrets out of the browser?

**Short answer:**
"The API key only ever exists in backend memory. Health and settings endpoints return booleans like `api_key_configured: true`, never the value. The frontend only knows a relative `/api` path."

**Deeper:** `.env` is git-ignored, only `.env.example` is committed, and CI runs without any secrets because tests use Mock mode.

---

### 15. Suppose traffic grows 100x. What breaks first?

**Short answer:**
"Two things. SQLite's single writer would serialise writes, and computing dashboard counts in Python by scanning rows gets slow. First fix: move to PostgreSQL with proper `GROUP BY` aggregates and indexes — `user_id`, `created_at`, `priority`, `status` are already indexed."

**Deeper:** then cache the dashboard response, add pagination everywhere (already server-side, 10–100 per page), and put AI calls in a background queue.

---

### 16. Why are `key_entities`, `action_items` and `observations` JSON columns instead of tables?

**Short answer:**
"Because their shape is produced by the AI and validated before storage. We read them as whole values and never filter or join on them, so a JSON column is simpler than four extra tables and one fewer join."

**Trade-off:** if we later needed *"find every document mentioning this entity"*, we'd normalise `key_entities` into its own table with a foreign key.

---

### 17. What does "Turn Documents into Decisions" mean in this app?

**Short answer:**
"It's the product pipeline. A document becomes a structured analysis, the analysis produces action items, and one click converts those into tracked tasks with owners and due dates — so information that would have sat in a file becomes work someone is accountable for."

---

# Part 2 — Backend / FastAPI (10)

### 18. What is dependency injection and where did you use it?

**Short answer:**
"A function declares what it needs and the framework supplies it. Every route takes `db: Session = Depends(get_db)` and `user: User = Depends(get_current_user)`, so auth is part of the signature — a route can't accidentally forget the check."

**Deeper:** `get_current_user` itself depends on `get_db`, so FastAPI reuses the same session rather than opening a second connection. It also makes tests trivial: `app.dependency_overrides[get_current_user] = fake_user`.

---

### 19. `Depends` vs `yield` — which did you use?

**Short answer:**
"`get_db` uses `yield`, because it must open a session, hand it to the route, and close it after the response. `get_current_user` is a plain `def` dependency — it just returns a value, so there's nothing to clean up."

**Deeper:** the `yield` form is what gives you per-request cleanup for free; forgetting `finally`-style cleanup there causes connection leaks.

---

### 20. What are Pydantic models used for here?

**Short answer:**
"As the contract at every boundary. Schemas validate incoming request bodies, define the exact JSON shape of every response, and — most importantly — validate what the AI returns before anything touches the database."

**Deeper:** `model_config = ConfigDict(from_attributes=True)` lets `DocumentDetail.model_validate(orm_row)` read directly from SQLAlchemy rows. Strict schemas are why a hallucinated `priority: "urgent"` gets normalised to `High` instead of saved.

---

### 21. Synchronous vs asynchronous endpoints — what did you choose and why?

**Short answer:**
"Route handlers are plain `def`, so FastAPI runs them in a threadpool and the event loop stays free. The one genuinely blocking thing — the AI call — runs in its own `ThreadPoolExecutor` with a timeout, so a slow provider can never stall other requests."

**Deeper:** the mistake to avoid is `async def` with blocking work inside it: that freezes the whole loop. Blocking + `def` is correct; blocking + `async def` is a bug.

---

### 22. How do you validate file uploads?

**Short answer:**
"Three checks, in order: extension allow-list (`.pdf`, `.txt`), size limit (10 MB), then the real content — a genuine PDF starts with the bytes `%PDF`. Only then do we extract text."

**Why the magic-byte check matters:** "Filename and MIME type are attacker-controlled — anyone can rename `malware.exe` to `report.pdf`. The first four bytes come from the file's content and can't be faked by renaming. There's a test, `test_upload_rejects_fake_pdf`, that proves it."

**Deeper:** TXT decoding tries `utf-8 → utf-8-sig → latin-1` because Windows users often save ANSI or UTF-16.

---

### 23. How do you protect against SQL injection?

**Short answer:**
"Parameterised queries through SQLAlchemy — I never build SQL from strings. User input becomes bound parameters, so it's data to the database rather than executable SQL."

**Deeper:** plus `ILIKE` escaping for search input, and ORM-level access everywhere. Raw SQL appears only where SQLAlchemy can parameterise it.

---

### 24. What does `get_current_user` actually do?

**Short answer:**
"Reads the `Authorization: Bearer` header, decodes and verifies the JWT signature and expiry, takes the `sub` claim, loads that user from the database, and returns it. Any failure — missing header, bad signature, expired token, deleted user — is a uniform 401."

**Deeper:** signature and expiry are checked *before* the DB hit, so forged tokens are rejected cheaply. The DB lookup afterwards handles deleted accounts.

---

### 25. What's the difference between `AppError` and letting exceptions bubble?

**Short answer:**
"Bubbling gives the client a 500 and, worse, risks leaking a stack trace. `AppError` carries a deliberate status code and a safe, human message. One handler converts it to `{"detail": ...}` so every failure has the same shape."

---

### 26. Why does the AI call use a thread pool instead of `async`?

**Short answer:**
"Because the Gemini SDK and the mock's delay are blocking calls. If I ran them inside `async def`, they'd block the event loop and every other request would hang. A worker thread keeps the loop responsive."

**Deeper:** `with ThreadPoolExecutor(max_workers=1)` is a single-use pool — the context manager guarantees the thread is cleaned up on timeout, so repeated timeouts can't leak threads. Timeout produces a 504.

---

### 27. How would you add a new endpoint? Walk me through it.

**Short answer:**
"Four steps. Define or reuse a schema in `schemas/`, write the logic in `services/` (including the `user_id` filter), add a thin route in `routers/`, and add a test. The router only parses the request and calls the service — no business logic there."

---

### 28. What does `pool_pre_ping=True` do?

**Short answer:**
"SQLAlchemy sends a lightweight `SELECT 1` before using a pooled connection. If the database restarted and the connection is stale, you get a fresh one instead of a `server has gone away` error."

**Deeper:** it's specifically valuable in Docker, where the backend may come up before PostgreSQL has settled.

---

# Part 3 — Database & SQLAlchemy (7)

### 29. Explain the relationships in your schema.

**Short answer:**
"One user has many documents and many tasks — both cascading, so deleting a user removes their data. A document has many optional tasks, and that link is `SET NULL`: deleting a report must not destroy the work it created. `tasks.document_id` is nullable for exactly that reason."

---

### 30. What's the difference between `delete-orphan` and `SET NULL`?

**Short answer:**
"`delete-orphan` removes the children with the parent — right for *user → documents*, because the data belongs to the account. `SET NULL` keeps the children but clears the reference — right for *document → tasks*, because the tasks are real work with owners and due dates."

**Deeper:** the delete dialog even tells the user: *"Tasks created from it are kept but lose their link."*

---

### 31. When would you use an outer join vs an inner join? Did you?

**Short answer:**
"Inner join when a match on both sides is required; outer join when you want the left side even without a match. I use both: the dashboard's document list is a plain inner join to the owner, while counting tasks per document uses a left join so a document with zero tasks still appears."

**Deeper:** the reverse case matters too — after a document deletion, tasks survive with `document_id = NULL`, so a query for "tasks and their document title" must be a *left* join from tasks.

---

### 32. How does pagination work?

**Short answer:**
"Server-side. The client sends `page` and `page_size` (10–100), the backend applies `LIMIT`/`OFFSET` with a `total` count, and returns `{items, total, page, pages}`. The browser never receives the whole table."

**Deeper:** changing any filter resets to page 1 — otherwise you'd land on page 5 of a one-page result and see an empty table.

---

### 33. Why index `user_id`, `created_at`, `priority`, `status`?

**Short answer:**
"Because every list query filters by `user_id` first and then sorts or filters by one of the others. An index on those columns turns a table scan into a direct lookup."

**Deeper:** `users.email` is unique-indexed, which also enforces the one-account-per-email rule at the database level, not just in code.

---

### 34. How do you handle migrations?

**Short answer:**
"`Base.metadata.create_all()` runs at startup so a beginner can launch with one command, and full Alembic scaffolding is included for when the schema actually starts evolving."

**Trade-off:** `create_all` never alters existing tables — it adds missing ones only. The moment you change a column, you need `alembic revision --autogenerate`.

---

### 35. What is `back_populates` and what happens if you forget it?

**Short answer:**
"It declares the inverse side of a relationship. If you set it on only one side, SQLAlchemy raises `InvalidRequestError: relationship 'Document.tasks' expects a corresponding relationship` at mapper configuration — startup fails loudly rather than silently misbehaving."

---

# Part 4 — Authentication & security (7)

### 36. How does authentication work end to end?

**Short answer:**
"Register hashes the password with bcrypt and stores it. Login verifies the hash and returns a signed JWT with `sub`, `exp`, `iat`. The frontend stores it in `localStorage` and an axios request interceptor attaches `Authorization: Bearer` to every call. The backend verifies signature and expiry on each request. A 401 triggers the response interceptor, which clears the token and redirects to `/login`."

---

### 37. Why bcrypt? What do the 12 rounds mean?

**Short answer:**
"Bcrypt is deliberately slow and salted — designed for passwords, not for fast hashing like MD5 or SHA-256. 12 rounds is roughly 250 ms per hash: imperceptible for one login, but a huge cost for an attacker doing billions of guesses."

**Deeper:** the salt is built into `gensalt`, so two identical passwords produce different hashes and rainbow tables don't work. We truncate to 72 bytes explicitly on both hash and verify, because bcrypt silently ignores bytes past 72 and we want that behaviour documented rather than surprising.

---

### 38. Why did you drop `passlib` and call `bcrypt` directly?

**Short answer:**
"passlib 1.7.4, the last release from 2019, reads `bcrypt.__about__.__version__`, which bcrypt 4.1 removed — it crashes at runtime. Rather than pinning an outdated library, I call the maintained `bcrypt` API directly. It's fewer dependencies and one less thing to break."

**Interview bonus:** this shows you check your dependency chain instead of copying old boilerplate.

---

### 39. Where do you store the JWT, and what's the trade-off?

**Short answer:**
"`localStorage`, because it survives refreshes and is simple to read, write and debug. The trade-off is that XSS could read it. An httpOnly cookie would close that hole but introduces CSRF, which needs its own protection."

**Deeper:** the honest framing is that both options have a cost; the mitigations are strict CSP and output escaping. The trade-off is written down in `documentation/02` rather than hidden.

---

### 40. JWT vs session cookies — which is better?

**Short answer:**
"Sessions are revocable and keep state server-side but need shared storage across instances. JWTs are stateless and scale horizontally but can't be revoked before expiry. For a small API with a token-per-device model, JWT is the simpler fit."

**Deeper:** if we needed "log out everywhere", sessions or a token denylist would win.

---

### 41. What is CORS and how did you handle it?

**Short answer:**
"CORS is the browser refusing cross-origin responses unless the server allows them. I mostly avoid it: the Vite and Nginx proxies make everything one origin. When a direct call is needed, `CORS_ORIGINS` is an explicit allow-list with credentials — never `*`."

---

### 42. Name a security vulnerability in this app and how you'd fix it.

**Short answer:**
"The clearest one is the JWT in `localStorage` — an XSS bug could steal it. Fix: move to httpOnly, SameSite cookies and add CSRF tokens. Other real ones worth naming: no rate limiting on `/login` (add Redis or Nginx `limit_req`), no TLS termination in this repo (put Caddy or Cloudflare in front), and stored XSS risk if AI-generated text were rendered as HTML — React escapes by default, but `dangerouslySetInnerHTML` would change that."

**Deeper:** naming a *real* weakness beats claiming perfection; interviewers are testing whether you know what you don't have.

---

# Part 5 — AI integration (5)

### 43. How do you handle LLM output being unreliable?

**Short answer:**
"Never trust it — validate everything. The model's JSON goes through a strict Pydantic schema that normalises some fields and rejects others. `priority: 'urgent'` becomes `High`; `priority: 'asap!!! '` is rejected; an unknown category falls back to `General Document` so frontend filters stay finite; an empty summary is rejected. If validation fails, the API returns 502 with a readable message instead of storing garbage."

**Deeper:** parsing itself is defensive — we extract the first JSON object from the response so surrounding prose can't break us.

---

### 44. What's the Mock AI mode, and why isn't it fake?

**Short answer:**
"It's a deterministic local engine that needs no API key. Keyword scoring picks the category, regexes extract emails, dates, money, phone numbers, URLs and reference IDs, urgency phrasing drives priority, and sentences with action verbs become action items. It's a real feature, not a stub — that's what makes demos, CI and interviews reproducible."

**Deeper:** every response carries `ai_provider: "mock"`, and the UI shows a permanent badge. Mock output is never passed off as Gemini output.

---

### 45. How would you add support for OpenAI?

**Short answer:**
"Two changes: create `services/openai_ai.py` returning the same dict shape as the other providers, and teach `ai_service.py` about it via a config flag. Routers, models, schemas and React don't change at all — because providers sit behind one contract."

---

### 46. How do you prevent one bad AI response from corrupting the database?

**Short answer:**
"Validation happens before persistence. The analysis is parsed and validated first; only a valid object reaches `document_service`. A failure raises `AppError` and nothing is written. The document row is created in the same commit as its extracted fields, so there's no partial state."

---

### 47. What happens when the AI provider times out?

**Short answer:**
"`future.result(timeout=30)` raises, the pool is shut down by its context manager, and the API returns 504 with a readable message like *'AI analysis exceeded the 30 second timeout'*. The frontend shows that message in a toast — the user isn't left with a spinner."

**Deeper:** 503 covers a missing API key or rate limit; 502 covers malformed output. Distinct codes make dashboards and alerting meaningful.

---

# Part 6 — Frontend / React (7)

### 48. Why React, and why no Redux or React Query?

**Short answer:**
"React because component model + ecosystem. I deliberately skipped Redux and React Query: the current user lives in one context, lists live in two custom hooks, and forms use local `useState`. For this size, hooks are easier to read and have zero boilerplate. I'd add a server-state library the moment caching or optimistic updates became real requirements."

---

### 49. Explain your custom hooks.

**Short answer:**
"`useDocuments` and `useTasks` return the same shape — `{filters, updateFilters, goToPage, refresh, items, loading, error}` — so both pages behave identically. The hook owns fetch state and query params; the page only deals with UI. Changing a filter resets to page 1, and `useCallback` keeps `load` stable so the effect dependencies stay honest."

**Deeper:** a recent fix added a request-sequence counter so an older slow response can't overwrite a newer filtered result — the classic out-of-order race.

---

### 50. What's the purpose of the axios interceptors?

**Short answer:**
"Two jobs in one place. The request interceptor attaches the token, so no component can forget `Authorization`. The response interceptor handles 401 uniformly — clear the token and redirect — and rewrites network failures into *'Cannot reach the server. Is the backend running on port 8001?'* instead of Axios's unhelpful `status code 0`."

---

### 51. How does route protection work?

**Short answer:**
"`ProtectedRoute` wraps the layout: if there's no authenticated user it redirects to `/login` while remembering where you were going, and Login navigates back there. `PublicOnly` does the reverse for `/login` and `/register`, so a signed-in user can't see the login page again."

**Deeper:** the `loading` state is essential — on refresh the token exists but the profile hasn't been fetched yet, and without it you'd get a flash of the login screen.

---

### 52. How do you handle loading, empty and error states?

**Short answer:**
"Every screen has all three. Loading shows a skeleton or spinner, empty shows a specific message — *'No tasks match your filters'* with a *Clear filters* button rather than a blank table — and errors show a readable sentence with a retry. Nothing ever renders as an unexplained blank area."

---

### 53. What is `useEffect` cleanup and where did you need it?

**Short answer:**
"The function returned from an effect runs on unmount. I need it for the debounced search — without `clearTimeout`, typing 'proposal' fires eight requests. It's also used for the 30-second health polling interval and for the Escape-key listener on modals, so neither leaks after unmount."

---

### 54. How would you make this app accessible?

**Short answer:**
"Already partly done: `aria-label` on icon-only buttons, `role="dialog"` and `aria-modal` on overlays, Escape closes them, real `<label htmlFor>` on every field, focus-visible rings, `role="status"` on loaders, and `prefers-reduced-motion` disables animation. Still to do: keyboard drag-and-drop on the board, focus trapping in modals, and live-region announcements after mutations."

**Naming what's missing** is what makes this answer credible.

---

# Part 7 — Testing, Docker & CI (6)

### 55. What tests do you have and what do they actually prove?

**Short answer:**
"142 pytest tests hitting the real app through `TestClient` — auth, documents, tasks, dashboard, AI, file handling, document types, chat and the provider-fallback chain. They prove behaviour, not implementation: another user's document returns 404 not 403, `hashed_password` never appears in any response, a duplicate task is rejected, and a fake PDF is refused."

**Deeper:** `conftest.py` points the app at a temp SQLite file, sets `MOCK_AI=true` *before* importing the app, empties every table around each test, and zeroes the mock delay so the suite runs in seconds.

---

### 56. What does test isolation mean here?

**Short answer:**
"Every test starts from an empty database, so test 17 can't depend on test 16. Env vars are set before `config.py` is imported, otherwise tests would silently hit my real development database — which is the most dangerous bug in a test suite because it doesn't fail, it just destroys data."

---

### 57. Explain multi-stage Docker builds.

**Short answer:**
"The first stage installs dependencies and compiles things; the second stage copies only the results. The backend ships a virtualenv without pip's cache, and the frontend ships `dist/` without Node. Smaller images, fewer installed tools, smaller attack surface — and dependency layers are still cached because `requirements.txt` is copied before the source."

---

### 58. What does the CI pipeline check?

**Short answer:**
"Two parallel jobs on every push and PR. Backend installs Python 3.12 and runs the 142 tests. Frontend installs Node 22 and runs a production build — that catches broken imports and JSX typos instantly. If either fails the workflow fails, so broken code can't merge."

**Deeper:** no secrets are needed since tests use Mock mode; dependencies are cached from the lock files; `cancel-in-progress` kills obsolete runs; pytest reports upload only on failure.

---

### 59. How does Docker Compose know to start the database first?

**Short answer:**
"`depends_on` with `condition: service_healthy`, backed by real healthchecks — `pg_isready` for PostgreSQL, `GET /api/health` for the backend, `wget /` for Nginx. Plain `depends_on` only waits for a container to *start*, which isn't the same as *ready* — without healthchecks the backend would crash trying to reach Postgres before it accepts connections."

---

### 60. Something works locally but fails in Docker. How do you debug?

**Short answer:**
"Same steps every time: `docker compose ps` to see which container isn't healthy, `docker compose logs <service>` for the actual error, confirm the environment variables the container received, then verify networking — the service name is the hostname, so it's `backend:8001` and `db:5432`, not `127.0.0.1`. Finally compare with local config, because the difference is almost always config rather than code."

**Common real causes here:** port 8000 already taken (we use 8001), Postgres not ready yet, and `DATABASE_URL` still pointing at SQLite.

---

# Part 8 — Tricky behavioural / scenario questions

### 61. What was the hardest bug you fixed in this project?

**Short answer (a real one from this codebase):**
"A race condition in the document list. Deep-linking to `/documents?search=quarterly` fired two overlapping requests — one with the filter, one without — and whichever *resolved* last won, so the unfiltered result could overwrite the filtered one. I fixed it with a request-sequence counter: each load increments a ref, and only the response matching the current sequence may write state. It also affected the tasks hook, so I applied it to both."

**Why this answer works:** it's specific, it names the mechanism, and it shows you understand *why* the bug happened rather than just patching it.

---

### 62. Tell me about a time you found a bug in your own code.

**Short answer:**
"During browser testing I found `h-4.5` in a component class — a Tailwind class that doesn't exist, so the icon silently fell back to an arbitrary size. I grepped the whole source for that pattern instead of fixing the one instance. It's a good example of why a visual check matters: no error, no test failure, just something slightly wrong."

---

### 63. How do you decide when a task is "done"?

**Short answer:**
"Definition of done for me: the feature works through the real UI, not just the API; there's a test covering the failure case too; the error and empty states are handled; it builds; and it's documented. For this project that meant running a full browser flow — register, analyze, convert to tasks, filter, delete — and confirming zero console errors."

---

### 64. A user uploads a 200 MB file. What happens?

**Short answer:**
"It's rejected before any processing. The backend validates size against `MAX_FILE_SIZE_MB` (10) and returns 400 with a readable message; the frontend checks first too so the user sees it instantly without wasting an upload. Nginx allows 12 MB (`client_max_body_size`) — just above our limit so our own error, not Nginx's, is what the user reads."

---

### 65. Two users request the same document id. What happens?

**Short answer:**
"Each only ever sees their own. The query filters on `user_id`, so the second user gets 404 — not 403, because 403 would confirm the id exists. Ownership is enforced in the service layer, which every route goes through."

---

### 66. How do you keep a codebase beginner-friendly?

**Short answer:**
"Structure you can read in one glance, one obvious place for each concern, comments that explain *why* rather than restating the line above, and no clever indirection. My test is simple: someone opens the folder and can find where to add a page, an endpoint or an API call within a minute — `documentation/02` literally ends with a 'where do I change X?' table."

---

### 67. What would you do with more time?

**Short answer:**
"Three things: Alembic migrations wired into CI so schema changes are reviewed, rate limiting and refresh tokens on auth, and Playwright end-to-end tests so the browser flow I ran manually by hand runs automatically on every push."

---

### 68. Why should we hire you for this role?

**Short answer:**
"Because I don't just make things work — I make them *verifiable*. This project has 142 tests, a CI pipeline, health checks, honest Mock/Real AI labelling, documented trade-offs instead of hidden ones, and I ran the whole thing through a real browser to confirm zero console errors before calling it finished."

---

# Part 9 — Document types, chat & deployment (5)

### 69. Why did you add a "document type" selector — isn't that just UI?

**Short answer:**
"No — it's enforced server-side. `document_type` is a real column on the documents table. When it's `general`, the service layer empties `action_items` before storage on every analyze/re-analyze path, so workflow tasks are impossible even if someone calls the API directly. The UI selector, the badge in the table, and the 'tasks disabled' note are just honest reflections of a rule the backend owns. That's the difference between hiding a button and enforcing a policy."

---

### 70. How does "chat with a document" work without hallucinating?

**Short answer:**
"The chat endpoint loads the stored extracted text of exactly one document — ownership-checked first, so a guessed id gets a 404. For long documents, a RAG layer chunks the text, embeds chunks with an independent embedding provider, retrieves the top-k relevant chunks, and grounds the answer in those. The system prompt forbids using outside knowledge. In Mock mode the answer is extractive — it returns the most relevant sentences or explicitly says the answer isn't in the document, so it physically cannot fabricate."

**Deeper:** embeddings record `provider`, `model` and `dimension` per vector, so switching embedding models triggers a clean re-embed instead of silently mixing incompatible vector spaces.

---

### 71. Your AI provider chain failed once in production — what did you do?

**Short answer:**
"Nothing manual — that's what the chain is for. Gemini's free tier was returning server errors, so the provider manager retried it, classified the failure as transient, and failed over to OpenRouter automatically. The response even carries `ai_provider_notice` so the UI can tell the user which provider answered and why. If every provider fails, the user gets an honest 502/503 with a readable message — never a fake result. Free-tier LLMs are unreliable by nature; the design assumes it."

---

### 72. How does PDF table extraction work, and what are its limits?

**Short answer:**
"`pdfplumber` is the primary engine because it understands layout coordinates — it keeps table rows and columns aligned — with `pypdf` as a fallback for files pdfplumber can't parse. The honest limits: no OCR, so scanned/image PDFs report 'no readable text', and extremely complex merged-cell layouts can still interleave. I verified it live with a table-heavy invoice PDF: line items, totals and dates all extracted correctly."

---

### 73. How would you deploy this for free without a credit card?

**Short answer:**
"Render Blueprint — `render.yaml` at the repo root provisions the FastAPI backend and the static React frontend from one GitHub repo. Secrets (`SECRET_KEY`, `DATABASE_URL`, API keys) are marked `sync: false` and entered in the dashboard, never committed. The database is a free managed Postgres from Neon or Supabase since Render's disk is ephemeral. GitHub Actions is the CI half — pytest plus a production build on every push — and Render's auto-deploy on push is the CD half."

---

## Quick-fire round (10 fast answers)

| # | Question | Answer |
|---|---|---|
| 1 | `DELETE /api/documents/999` for another user's doc? | `404` — never confirm it exists |
| 2 | Duplicate registration? | `400` with a readable message (some APIs use `409`) |
| 3 | Expired JWT? | `401` → interceptor clears token → redirect `/login` |
| 4 | AI returns invalid JSON? | `502`, nothing persisted |
| 5 | AI takes 45s? | `504` after the 30s timeout, pool cleaned up |
| 6 | Missing `GEMINI_API_KEY` with `MOCK_AI=false`? | `503`, message tells you which env var |
| 7 | Where's the base URL defined? | `frontend/src/services/api.js` — one file, relative `/api` |
| 8 | Add a page? | new `src/pages/X.jsx` + one line in `routes/AppRoutes.jsx` |
| 9 | Add an endpoint? | `routers/` + `services/` + a test |
| 10 | Backend port? | **8001** (frontend dev 5173, Docker 8080 — never 8000) |

---

## How to answer system-design questions with this project

Use the **S-T-R** frame:

- **S — Situation:** *"Users need to turn reports into tracked work."*
- **T — Task:** *"One endpoint that validates a file, runs AI, and stores a structured analysis."*
- **R — Result:** *"Multipart validation with magic-byte checks, a provider-agnostic AI service behind a strict schema, `SET NULL` so tasks survive document deletion, 142 tests and CI proving it."*

And always end with the **trade-off**, e.g.: *"The cost of that design is a slightly larger response payload — but at this scale, correctness beats cleverness."*

---

*Back to [01 — Project Architecture](01_project_architecture.md).*
