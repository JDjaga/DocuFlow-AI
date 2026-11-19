# DocuFlow AI — Code Concepts Explained

> **Document 2 of 6** · [Architecture](01_project_architecture.md) · [Docker & CI/CD](03_docker_cicd.md) · [Interview Q&A](04_interview_qa.md) · [Checklist](05_verification_checklist.md) · [AI Providers](06_ai_providers.md)

This document explains the **programming concepts used in this project**, each one tied to the actual file where you can see it. It is written so a beginner can follow along with the code open.

---

## Table of contents

1. [Backend concepts](#part-a--backend-concepts)
   - [Environment-based configuration](#1-environment-based-configuration)
   - [Dependency injection](#2-dependency-injection-fastapi-depends)
   - [The repository/service/router layering](#3-repositoryservice-router-layering)
   - [SQLAlchemy 2.0 typed ORM](#4-sqlalchemy-20-typed-orm)
   - [Relationships & cascades](#5-relationships--cascades)
   - [Pydantic v2 schemas](#6-pydantic-v2-schemas)
   - [Password hashing with bcrypt](#7-password-hashing-with-bcrypt)
   - [JWT authentication](#8-jwt-authentication)
   - [Multipart uploads & file validation](#9-multipart-uploads--file-validation)
   - [Exception handling & typed errors](#10-exception-handling--typed-errors)
   - [The AI service boundary](#11-the-ai-service-boundary)
   - [Thread pool + timeout (per provider attempt)](#12-thread-pool--timeout-per-provider-attempt)
   - [Testing with fixtures](#13-testing-with-fixtures)
2. [Frontend concepts](#part-b--frontend-concepts)
   - [Vite & the dev proxy](#14-vite--the-dev-proxy)
   - [React context for auth](#15-react-context-for-auth)
   - [Custom hooks](#16-custom-hooks)
   - [Axios interceptors](#17-axios-interceptors)
   - [React Router & route guards](#18-react-router--route-guards)
   - [Controlled forms & validation](#19-controlled-forms--validation)
   - [Debounced search](#20-debounced-search)
   - [URL as state](#21-url-as-state)
   - [Optimistic-ish refresh pattern](#22-refresh-after-mutation)
   - [Tailwind component classes](#23-tailwind-component-classes)
   - [Accessibility basics](#24-accessibility-basics)

---

# PART A — Backend concepts

## 1. Environment-based configuration

**Concept:** never hardcode secrets, ports or keys — read them from the environment.

**Where:** `backend/app/core/config.py`

```python
class Settings(BaseSettings): # pydantic-settings
    SECRET_KEY: str = "dev-secret-change-me-in-production"
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'docuflow.db'}"
    MOCK_AI: bool = True
    ...

settings = get_settings()   # built once, cached
```

**Why it matters:**
- The *same code* runs locally (SQLite + Mock AI) and in Docker (PostgreSQL + optional Gemini) — only the environment changes.
- Secrets live in `.env` files that are **git-ignored** (see `.gitignore`), so they can never leak through a commit.
- Values are **typed**: `MOCK_AI="false"` is parsed as boolean `False`, not the truthy string `"false"`.

**Beginner trap:** a common bug is reading `os.environ` at import time in many files. Centralising it in one `Settings` object means there is exactly one place to look when a value is wrong.

---

## 2. Dependency injection (FastAPI `Depends`)

**Concept:** a function declares what it needs; the framework supplies it.

**Where:** every router, e.g. `backend/app/routers/documents.py`

```python
@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),              # ← a DB session
    user: User = Depends(get_current_user),     # ← the logged-in user
):
    ...
```

**What FastAPI does:**

```
request arrives
   │
   ├─ needs get_db()        → opens a session, yields it, closes after response
   ├─ needs get_current_user→ reads Authorization header, decodes JWT,
   │                          loads User from DB (itself uses get_db)
   └─ then calls list_documents(db, user)
```

**Why it matters:**
- **No route can forget the auth check** — it is part of the signature.
- `get_current_user` itself depends on `get_db`, so the framework reuses the *same* session instead of opening a second connection.
- Everything is easy to test: `app.dependency_overrides[get_current_user] = fake_user`.

---

## 3. Repository/service/router layering

**Concept:** separate *HTTP shape* from *business rules* from *storage*.

```
routers/      → parse request, call a service, return JSON      (thin!)
services/     → business rules, queries, validation             (the brain)
models/       → table definitions
schemas/      → the JSON contract (what may go in / out)
```

**Example — deleting a document** (`routers/documents.py` → `services/document_service.py`):

```python
# router: only HTTP concerns
@router.delete("/{document_id}", response_model=Message)
def delete_document(document_id, db=Depends(get_db), user=Depends(get_current_user)):
    document_service.delete_document(db, user, document_id)
    return Message(detail="Document deleted successfully.")

# service: the actual rule — unlink tasks first, then delete
def delete_document(db, user, document_id):
    document = get_owned_document(db, user, document_id)   # 404 if not yours
    for task in db.execute(select(Task).where(Task.document_id == document.id)):
        task.document_id = None                            # keep the work
    db.delete(document)
    db.commit()
```

**Why it matters:** the service can be unit-tested without HTTP, and the same service could back a CLI or a future GraphQL API.

---

## 4. SQLAlchemy 2.0 typed ORM

**Concept:** map Python classes to database tables with full type hints.

**Where:** `backend/app/models/document.py`

```python
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    key_entities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
```

**Details worth knowing:**
- `Mapped[...]` types drive both Python validation and the generated DDL.
- `default=` runs in Python; `server_default=` runs in the database (used so raw SQL inserts also work).
- `index=True` on `user_id` / `email` / `priority` — every list query filters by these.
- `JSON` columns store AI output as-is; SQLAlchemy converts dict ⇄ JSON automatically.

---

## 5. Relationships & cascades

**Concept:** declare how tables reference each other and what deletion does.

**Where:** `models/user.py`, `models/document.py`, `models/task.py`

```python
# User side
documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
tasks     = relationship("Task",     back_populates="owner", cascade="all, delete-orphan")

# Document side
owner = relationship("User", back_populates="documents")
tasks = relationship("Task", back_populates="document")

# Task side (nullable FK!)
document_id: Mapped[int | None] = mapped_column(FK("documents.id", ondelete="SET NULL"))
```

**The two cascade choices:**

| Relationship | Cascade | Meaning |
|---|---|---|
| User → Documents/Tasks | `delete-orphan` | deleting a user removes their data (GDPR-friendly) |
| Document → Tasks | `SET NULL` | deleting a *report* must not destroy the *work* it created |

**Why `back_populates` must exist on BOTH sides:** forgetting one side raises `InvalidRequestError: relationship 'Document.tasks' expects a corresponding relationship` — a classic beginner error this project deliberately avoids.

---

## 6. Pydantic v2 schemas

**Concept:** a strict, declarative contract for JSON — the gatekeeper between the outside world and your code.

**Where:** `backend/app/schemas/ai.py` (the most interesting one)

```python
class AIAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    priority: str
    category: str

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value): return _normalise_priority(value)
```

**Why this file exists:** LLMs return *inventive* JSON. Before anything is stored:

- `priority: "urgent"` → normalised to `"High"` (aliases table)
- `priority: "asap!!! "` → **rejected** → the API answers 502 instead of saving garbage
- `category: "Space Novel"` → falls back to `"General Document"` so frontend filters stay finite
- `summary: ""` → rejected (a document with no summary is a bug, not data)

`model_config = ConfigDict(from_attributes=True)` lets Pydantic read directly from an ORM row: `DocumentDetail.model_validate(document)`.

---

## 7. Password hashing with bcrypt

**Concept:** one-way transformation — you can verify a password but never recover it.

**Where:** `backend/app/core/security.py`

```python
BCRYPT_ROUNDS = 12
PASSWORD_MAX_BYTES = 72

def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:PASSWORD_MAX_BYTES]
    return hashpw(truncated, gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")
```

**Four things this code gets right:**

1. **Salt is built into bcrypt** (`gensalt` generates it) — two identical passwords produce *different* hashes, defeating rainbow tables.
2. **12 rounds** ≈ 250 ms per hash — expensive for an attacker doing billions of guesses, imperceptible for a login.
3. **Explicit 72-byte truncation** — bcrypt silently ignores bytes after 72; truncating on *both* hash and verify keeps behaviour identical and documented.
4. **Never stored in responses** — `UserOut` schema simply does not have a `hashed_password` field; a test asserts it.

> **Why not passlib?** passlib 1.7.4 (the last release, 2019) reads `bcrypt.__about__.__version__`, which bcrypt ≥ 4.1 removed — it crashes at runtime. Calling the well-maintained `bcrypt` library directly removes a broken dependency. *Interview bonus: this shows you check your dependency chain instead of copying old boilerplate.*

---

## 8. JWT authentication

**Concept:** a signed, expiring token that proves identity without a server session.

**Token contents (HS256):**

```json
{ "sub": "42", "email": "asha@example.com",
  "exp": 1763400000, "iat": 1763313600 }
```

**Flow:**

```
login ──▶ verify password ──▶ create_access_token(user.id) ──▶ JSON to browser
                                                                    │
every later request: Authorization: Bearer <token>                  │
        │                                                           │
        ▼                                                           ▼
decode_access_token()  ──  signature valid?  exp passed?  user exists?
        │ no ────────────────────────────────────▶ 401 (clear token in UI)
        │ yes
        ▼
   get(User, sub) ──▶ route handler receives `user`
```

**Key points:**
- The token is **signed, not encrypted** — anyone can *read* the payload, so never put secrets in it (no password hash!).
- **Stateless verification:** the server checks the signature and expiry without a DB hit; only then does it load the user (to handle deleted accounts).
- `decode_access_token` returns `None` on *any* `JWTError` (expired, tampered, malformed) → uniform 401.
- A test asserts an unknown email and a wrong password return the **same** message, so the API cannot be used to discover registered emails.

---

## 9. Multipart uploads & file validation

**Concept:** uploaded files are untrusted input — validate *content*, not names.

**Where:** `services/file_service.py` + `utils/file_validation.py`

```
request (multipart/form-data)
   │
   ├─ validate_extension()      ".pdf" ".txt" allow-list
   ├─ validate_size()           ≤ MAX_FILE_SIZE_MB (10)
   ├─ validate_signature()      content must start with %PDF   ← the important one
   ├─ extract text              pypdf for PDF, utf-8/latin-1 for TXT
   └─ MAX_INPUT_CHARS guard     ≤ 40,000 characters
```

**Why the magic-byte check matters:** an attacker renames `malware.exe` → `report.pdf`. The filename and even the browser's MIME type are attacker-controlled. The first four bytes of a genuine PDF are `%PDF` — that comes from the file's *content* and cannot be faked by renaming. A test (`test_upload_rejects_fake_pdf`) proves it.

**Encoding tolerance for TXT:** Windows users often save as UTF-16/ANSI; the code tries `utf-8 → utf-8-sig → latin-1` and only then reports a friendly error.

---

## 10. Exception handling & typed errors

**Concept:** one custom exception class → one JSON shape → one frontend helper.

**Where:** `utils/errors.py` + `main.py`

```python
class AppError(Exception):
    def __init__(self, detail, status_code=400): ...

# main.py
@app.exception_handler(AppError)
async def handle_app_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

**The three safety nets:**

| Layer | Handles | Client sees |
|---|---|---|
| `AppError` | our known failures | `{"detail": "Document not found."}` + correct status |
| `RequestValidationError` | Pydantic 422 | readable `title: Field required` |
| `Exception` (catch-all) | anything unexpected | `"An unexpected server error occurred."` — **never a stack trace** |

Status codes are *chosen*, not defaulted: 409 for duplicate email, 404 for cross-user access, 502 for bad AI output, 503 for missing API key, 504 for AI timeout. The frontend's `getErrorMessage()` reads `detail` and shows it in a toast.

---

## 11. The AI service boundary

**Concept:** isolate a whole family of third-party dependencies behind one function with a typed result.

**Where:** `services/ai_service.py` → `services/ai/provider_manager.py`

```python
def analyze_text(text: str) -> tuple[AIAnalysis, str, str | None]:
    """Returns (validated analysis, actual provider, fallback notice)."""
    def _call(provider):
        result = provider.generate_analysis(text)
        result.data = validate_analysis(result.data)   # runs INSIDE the manager
        return result

    outcome = manager.execute("analyze_document", _call)   # retries + fallback
    return outcome.result.data, outcome.result.provider, outcome.notice
```

**Why this design is interview gold:**

- **Swap-ability:** every provider (`mock_provider`, `gemini_provider`, `openrouter_provider`, `ollama_provider`) implements the same `AIProvider` interface and returns the same `ProviderResult`. Adding OpenAI = one new file + one line in `build_provider_chain()` — routers and React never change.
- **One fallback layer, not N:** no endpoint knows about providers. `provider_manager.execute()` owns the chain, retries (`AI_MAX_RETRIES`, exponential backoff), the transient-error taxonomy and the metrics log — the *same* logical operation, different provider.
- **Validation is central and inside the chain:** `_validate()` converts *any* malformed model output into a typed error **inside the manager call**, so a garbled Gemini JSON reply falls back to the next provider instead of failing the user's request. Invalid user input raises `InvalidInputError` immediately and **never** falls back.
- **Honesty:** the result travels with the provider that actually answered (`ai_provider: "gemini" | "openrouter" | "ollama" | "mock"`) plus `ai_provider_notice` when fallback happened, so the UI can label it — mock output is never passed off as Gemini.

---

## 12. Thread pool + timeout (per provider attempt)

**Concept:** never let a slow external call block the server.

**Where:** `services/ai/provider_manager.py` → `_call_with_timeout()`

```python
def _call_with_timeout(self, fn):
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-mgr") as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=self.timeout_seconds)   # AI_REQUEST_TIMEOUT=60
        except FutureTimeoutError as exc:
            raise _timeout_error(self.timeout_seconds) from exc  # category "timeout" → 504
```

**Why not `async`?** The provider SDKs and HTTP calls are blocking. Running them directly inside `async def` would freeze the *entire* event loop — every other request would hang. A worker thread keeps the loop free.

**Why `with` (context manager)?** On timeout the pool is shut down deterministically, so the worker thread is cleaned up. A naive global pool can leak threads after repeated timeouts.

**Why `max_workers=1`?** Each attempt creates a single-use pool — no queueing surprises, no shared state, complete isolation.

**How it fits the chain:** the timeout applies to **one provider attempt**, not the whole request. A `timeout` is a *transient* error category, so after `AI_MAX_RETRIES` attempts the manager moves to the next provider instead of immediately failing the user.

---

## 13. Testing with fixtures

**Concept:** arrange shared state once, isolate every test, assert behaviour.

**Where:** `backend/tests/conftest.py`

```python
# MUST run before `app` is imported — config.py reads env at import time
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["MOCK_AI"] = "true"

@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    _clean_tables()                 # empty DB before AND after each test
    with TestClient(app) as c:
        yield c
    _clean_tables()
```

**The three rules this file follows:**

1. **Env before import.** If `.env` were read first, tests would hit the developer's real database.
2. **Total isolation.** Every table is emptied around each test, so test #17 cannot depend on test #16.
3. **Deterministic AI.** `mock_ai.MOCK_DELAY_SECONDS = 0.0` removes the demo animation delay, and Mock mode means no API key, no network, no cost.

**Good assertions in this suite:**
- `assert "hashed_password" not in response.text` (leak check)
- `assert other_user_gets == 404` (isolation, not 403)
- `assert duplicate.status_code == 400` (idempotency protection)
- `make_pdf()` builds a *real* PDF byte-by-byte so extraction is genuinely tested without another dependency.

---

# PART B — Frontend concepts

## 14. Vite & the dev proxy

**Concept:** a dev server that serves your app and forwards API calls, so the browser sees one origin.

**Where:** `frontend/vite.config.js`

```js
server: {
  port: 5173,
  proxy: { '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true } },
}
```

**The problem it solves:**

```
WITHOUT proxy:  http://localhost:5173  ──fetch──▶ http://127.0.0.1:8001  = CORS error
WITH proxy:     http://localhost:5173/api/...  ──▶ Vite server ──▶ backend   = same origin
```

Because `VITE_API_URL` is **empty in dev**, `services/api.js` builds `baseURL = "/api"` — relative URLs always hit the same origin, which is the proxy. In Docker, Nginx does the identical job. **Result: zero CORS configuration for developers, and the backend URL is a deployment detail.**

---

## 15. React context for auth

**Concept:** share data that *many* components need without prop-drilling.

**Where:** `frontend/src/context/AuthContext.jsx`

```jsx
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {            // restore session on refresh
    if (!getToken()) { setLoading(false); return; }
    fetchCurrentUser().then(setUser).catch(() => setUser(null))
                       .finally(() => setLoading(false));
  }, []);

  const value = useMemo(() => ({ user, loading, signIn, signUp, signOut }), [...]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

**Why `loading` is essential:** on a page refresh there is a brief moment where the token exists but the profile has not been fetched yet. Without `loading`, `ProtectedRoute` would wrongly bounce the user to `/login` — a classic "flash of login screen" bug. The route shows a loader instead.

**Why `useMemo`:** without it a new object identity is created every render, re-rendering every consumer of the context.

---

## 16. Custom hooks

**Concept:** extract *stateful* logic into reusable functions that look like components to React.

**Where:** `frontend/src/hooks/useDocuments.js` (and `useTasks.js` — same shape)

```js
export default function useDocuments(initialFilters = {}) {
  const [filters, setFilters] = useState({...DEFAULT_FILTERS, ...initialFilters});
  const [data, setData] = useState({ items: [], total: 0, ... });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (currentFilters) => { ... listDocuments(params) ... }, []);

  useEffect(() => { load(filters); }, [filters, load]);   // refetch on change

  const updateFilters = useCallback((patch, { keepPage = false } = {}) => {
    setFilters(prev => ({ ...prev, ...patch, page: keepPage ? prev.page : 1 }));
  }, []);

  return { filters, updateFilters, goToPage, refresh, ...data, loading, error };
}
```

**Why it matters:**
- The **page component only deals with UI**; it never builds query params or manages fetch state.
- Changing any filter **automatically resets to page 1** — otherwise you would land on page 5 of a 1-page result and see an empty table.
- Documents and Tasks return the *identical* shape, so both screens behave consistently (and you only learn one pattern).
- `useCallback` keeps `load` stable, which keeps the `useEffect` dependency array honest.

---

## 17. Axios interceptors

**Concept:** cross-cutting request/response logic in one place.

**Where:** `frontend/src/services/api.js`

```js
// request: attach the token
client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// response: global error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && getToken()) {
      clearToken();
      window.location.assign('/login');          // session expired
    }
    if (!error.response) error.friendlyMessage = 'Cannot reach the server. Is the backend running on port 8001?';
    return Promise.reject(error);
  }
);
```

**Two wins:**
1. **No component ever touches the token** — forgetting `Authorization` is impossible.
2. **One 401 handler** instead of 20 — every expired session behaves identically: clear token, explain, redirect.

Note the network-failure branch: `error.response` is `undefined` when the server is down, and that case needs a friendlier message than Axios's default `Request failed with status code 0`.

---

## 18. React Router & route guards

**Concept:** declarative URL → component mapping with protection wrappers.

**Where:** `frontend/src/routes/AppRoutes.jsx`

```jsx
<Routes>
  <Route path="/login"    element={<PublicOnly><Login/></PublicOnly>} />
  <Route element={<ProtectedRoute />}>            {/* auth gate */}
    <Route element={<AppLayout />}>               {/* sidebar + topbar shell */}
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<Dashboard />} />
      ...
      <Route path="*" element={<NotFound />} />
    </Route>
  </Route>
</Routes>
```

**Three nesting tricks:**
- **Layout routes** (`<Route element={...}>` without `path`) wrap children — one place for the shell, one place for the guard.
- **`<Outlet />`** is where the child route renders.
- **`index` route** handles `/` without a redirect loop.

**`ProtectedRoute` remembers the destination:**

```jsx
if (!isAuthenticated) return <Navigate to="/login" state={{ from: location.pathname }} />;
```

…and Login navigates back to `location.state?.from`. *You click "Documents", get asked to log in, and land on Documents* — a small detail that feels professional.

---

## 19. Controlled forms & validation

**Concept:** React owns every input's value; validate before hitting the network.

**Where:** `frontend/src/pages/Login.jsx` + `utils/validators.js`

```jsx
const [values, setValues] = useState({ email: '', password: '' });

async function handleSubmit(event) {
  event.preventDefault();
  const errors = validateLogin(values);       // instant, no round trip
  setErrors(errors);
  if (Object.keys(errors).length) return;     // stop here
  await signIn(values.email, values.password);
}
```

**Two-tier validation (deliberate duplication):**

| Tier | Where | Purpose |
|---|---|---|
| Client | `utils/validators.js` | instant feedback, no wasted request |
| Server | Pydantic schemas | **the real gate** — never trust the client |

The client rules *mirror* the server (password ≥ 8, confirm must match), so the UX is fast — but a modified client still gets a proper 422. Error state is cleared per-field as the user types (`setErrors(prev => ({...prev, [name]: ''}))`), which is the behaviour people expect from good forms.

---

## 20. Debounced search

**Concept:** wait for the user to *stop typing* before firing a request.

**Where:** `frontend/src/components/common/SearchInput.jsx`

```jsx
useEffect(() => {
  if (localValue === value) return;            // nothing new to send
  const timer = setTimeout(() => onSearch(localValue), 350);
  return () => clearTimeout(timer);             // ← cleanup cancels the pending call
}, [localValue, value, onSearch, debounceMs]);
```

**Why the `cleanup` return is critical:** without `clearTimeout`, typing "proposal" fires **8 requests**; with it, only the one after 350 ms of silence. The `if (localValue === value) return` guard prevents an infinite loop — `value` is updated by the parent, which would otherwise re-trigger the effect forever.

---

## 21. URL as state

**Concept:** put shareable state in the query string so links work and refresh behaves.

**Where:** `frontend/src/pages/Documents.jsx`

```
/documents?search=contract     ← the global top-bar search lands here
/documents?open=42             ← "View" from the Dashboard opens the drawer
```

```jsx
const [searchParams, setSearchParams] = useSearchParams();

useEffect(() => {
  const urlSearch = searchParams.get('search');
  if (urlSearch && urlSearch !== filters.search) updateFilters({ search: urlSearch });
  const openId = searchParams.get('open');
  if (openId) getDocument(Number(openId)).then(setSelected)...;
}, [searchParams]);
```

**Why it feels good:** you can send a colleague a link to *exactly* your filtered view, the browser Back button undoes navigation, and after a refresh the drawer does **not** reopen (the `open` param is deleted with `replace: true`).

---

## 22. Refresh-after-mutation

**Concept:** after any write, re-fetch instead of hand-patching state.

**Where:** Tasks/Documents pages

```jsx
async function handleStatusChange(task, nextStatus) {
  await updateTask(task.id, { status: nextStatus });
  toast.success('Task moved to in review.');
  refresh();                       // ← re-run the current query
}
```

**Why not update local state by hand?** A mutation can change *many* derived values: row order, status-tab counts, pagination totals, dashboard KPIs. Re-fetching guarantees every one of them is consistent with the server. At this scale one extra GET is far cheaper than reasoning about every side effect.

**Why not full page reload?** `refresh()` re-runs the hook's `load()` — the React tree stays mounted, filters are preserved, and the user does not lose their place.

---

## 23. Tailwind component classes

**Concept:** define the design system once in CSS, use short classes everywhere.

**Where:** `frontend/src/index.css`

```css
@layer components {
  .input { @apply w-full rounded-lg border border-slate-300 px-3.5 py-2.5 ... focus:ring-4; }
  .btn-primary { @apply btn bg-indigo-600 text-white hover:bg-indigo-700; }
  .th { @apply px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide; }
}
```

**Why:** every text field shares the same focus ring, radius and padding because there is *one definition*. Changing the brand colour touches one line instead of 40 files. It also keeps JSX readable: `className="input"` beats a 150-character utility string.

---

## 24. Accessibility basics

Small touches included throughout:

| Practice | Where |
|---|---|
| `aria-label` on icon-only buttons | Sidebar collapse, row actions, menus |
| `aria-modal="true"` + `role="dialog"` | Modal, DocumentDrawer |
| Escape closes overlays | `Modal`, `DocumentDrawer` (with cleanup) |
| Focus-visible ring | `*:focus-visible` in `index.css` |
| `prefers-reduced-motion` | disables all animation for users who ask for it |
| Real `<label htmlFor>` | every form field |
| `role="status"` on loaders | screen readers announce loading |
| Keyboard-reachable inputs | hidden file input behind the drag & drop zone |

---

## 25. Document types — `task` vs `general` (server-enforced)

**Concept:** a persisted classification column drives which features a document gets — enforced in the service layer, not just hidden in the UI.

**Where:** `app/models/document.py` (`document_type`), `app/services/document_service.py`, `app/routers/documents.py` (multipart field), `src/pages/Analyzer.jsx` (selector), `src/components/documents/{AiResults,DocumentDrawer,DocumentTable}.jsx`

```python
# document_service.analyze_document (simplified)
if document_type == "general":
    analysis.action_items = []        # workflow tasks impossible
# ... validate document_type in {"task","general"} → 400 otherwise
```

- `POST /api/documents/analyze` accepts `document_type`; `PUT /api/documents/{id}` can reclassify. Invalid values → 400.
- `general` ⇒ summary, category, entities, priority, observations **and chat** still work — only action items / task creation are disabled.
- The frontend reflects it honestly: Analyzer shows two selector cards, results/drawer show a "tasks disabled" note, and the Documents table has a Type column.

## 26. Chat with documents — grounded Q&A + RAG

**Concept:** the same provider chain answers questions, but the *context* is one stored document — optionally narrowed by embedding-based retrieval.

**Where:** `app/routers/chat.py` → `app/services/chat_service.py` → `app/services/rag_service.py` + `services/ai/embedding_service.py`

```
POST /api/documents/{id}/chat   { "question": "..." }
        │
        ▼  get_owned_document()  → 404 for other users' docs
   document.extracted_text  (+ best-matching chunks if embeddings exist)
        │
        ▼  provider_manager.execute("chat", ...)
   gemini/openrouter/ollama  — system prompt: "use ONLY this document"
        │
        ▼
   { answer, provider, sources[] }   ← citations shown as chips in the UI
```

- **Ownership first:** the document is loaded through the same `get_owned_document()` used everywhere — a guessed id returns 404.
- **Honest fallback:** the Mock engine (`mock_ai.answer_question`) is *extractive* — it returns the most relevant sentences or explicitly says the answer isn't in the document, so it can never fabricate.
- **RAG (optional layer):** `rag_service` chunks long texts, embeds chunks via the independent embedding chain, and retrieves top-k chunks for the question. Each stored embedding records `provider`/`model`/`dimension` — a model change re-embeds rather than mixing vector spaces. Short documents skip retrieval entirely.
- **Frontend:** `DocumentChat.jsx` renders in the Analyzer results and the Document drawer; `services/chat.js` is the only file that knows the endpoint.

## Quick reference — "where do I change X?"

| I want to… | File |
|---|---|
| add a backend endpoint | `app/routers/<area>.py` + `app/services/<area>_service.py` |
| change a table | `app/models/*.py` (+ Alembic migration later) |
| change what the AI returns | `app/schemas/ai.py` |
| change document types / task rules | `app/core/constants.py` + `app/services/document_service.py` + `src/utils/constants.js` |
| change chat behaviour / RAG | `app/services/chat_service.py` + `app/services/rag_service.py` |
| add an AI provider | new `app/services/ai/<name>_provider.py` (implements `AIProvider`) + one line in `provider_manager.build_provider_chain()` |
| add a frontend page | `src/pages/X.jsx` + one line in `src/routes/AppRoutes.jsx` |
| add an API call | `src/services/<area>.js` |
| change a shared UI rule | `src/index.css` (`@layer components`) |
| change statuses/priorities | `app/core/constants.py` **and** `src/utils/constants.js` (keep in sync!) |

---

*Continue with [03 — Docker & CI/CD](03_docker_cicd.md).*
