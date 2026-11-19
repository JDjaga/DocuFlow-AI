# DocuFlow AI — Multi-Provider AI Setup

> How the AI layer works, how to configure each provider, and how to test it.
> Companion to the code in `backend/app/services/ai/` and `backend/app/services/rag_service.py`.

---

## 1. Architecture at a glance

```
routers/documents.py ─┐
routers/chat.py ──────┼──► services/ai/provider_manager.py ──► Gemini
                      │        (ONE fallback layer)        ──► OpenRouter
services/ai_service.py┘        retries · notices · metrics ──► Ollama
                                                             ──► Mock (MOCK_AI=true only)

document_service ──► services/rag_service.py ──► embedding_service.py   (INDEPENDENT)
                      chunk · store · retrieve ──► gemini | local | mock embeddings
```

Two separate pipelines on purpose:

| Pipeline | Purpose | Providers |
|---|---|---|
| **Generation** | analysis, summaries, chat answers | Gemini → OpenRouter → Ollama (priority chain) |
| **Embeddings** | chunk vectors for RAG retrieval | `EMBEDDING_PROVIDER` = `auto \| gemini \| local \| mock` |

Embeddings never trigger generation fallback, and generation never changes
the embedding model mid-document.

### Key rules

- **One fallback layer.** No endpoint contains provider logic. Everything
  calls `provider_manager.execute(operation, call)`.
- **Fallback only on transient errors:** 429 / quota / 5xx / connection /
  timeout / provider auth / malformed model output.
  **Never** on invalid input (400-class), never on business errors.
- **Mock is never a silent fallback.** `MOCK_AI=true` → the chain is
  `[Mock]` only. `MOCK_AI=false` → mock is excluded even if listed in
  `AI_PROVIDER_PRIORITY`.
- **Retries** (`AI_MAX_RETRIES`, exponential backoff) happen on the *same*
  provider first; only then does the chain move to the next one.
- **Schema validation runs inside the manager call** — a malformed JSON
  reply from Gemini falls back to OpenRouter instead of erroring the user.
- **Notices are honest:** when a fallback really happened, the API returns
  `ai_provider_notice` / `provider_notice`
  (e.g. *"Google Gemini quota was exhausted. OpenRouter was used for this
  request."*) and the UI shows it as a toast/banner.

---

## 2. Environment variables (spec §6)

Copy `backend/.env.example` → `backend/.env` (local) or root
`.env.example` → `.env` (Docker). `.env` is git-ignored — never commit it.

```env
# --- Priority & reliability -------------------------------------
AI_PROVIDER_PRIORITY=gemini,openrouter,ollama
AI_MAX_RETRIES=2              # per provider, exponential backoff
AI_REQUEST_TIMEOUT=60         # seconds per provider attempt
AI_FALLBACK_ENABLED=true      # false = first provider only

# --- Google Gemini (primary) ------------------------------------
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# --- OpenRouter (fallback) --------------------------------------
OPENROUTER_API_KEY=
OPENROUTER_MODEL=                     # e.g. meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_FALLBACK_MODELS=           # comma-separated backup ids
OPENROUTER_FREE_MODELS_ONLY=true      # NEVER silently use a paid model
OPENROUTER_ALLOWED_MODELS=            # optional explicit allowlist (wins over :free)
OPENROUTER_MAX_SPEND=0                # USD monthly cap; 0 = no limit

# --- Ollama (optional local) ------------------------------------
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=                         # e.g. qwen2.5:1.5b

# --- Embeddings (independent from generation) -------------------
EMBEDDING_PROVIDER=auto               # auto | gemini | local | mock
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# --- Mode -------------------------------------------------------
MOCK_AI=true                          # true = Mock only (dev/tests/CI)
```

**Startup validation** (`main.py` lifespan → `settings.validate_ai_settings()`):

- malformed values (unknown provider name, negative retries, timeout ≤ 0,
  unknown `EMBEDDING_PROVIDER`) → the app **refuses to start** with a clear error;
- incomplete-but-valid setups (e.g. `MOCK_AI=false` with no key) → logged as
  warnings, the app still starts and reports `unavailable` on `/api/health/ai`.

---

## 3. Setting up each provider

### 3.1 Google Gemini (primary)

1. Create a key at <https://aistudio.google.com/apikey>.
2. ```env
   MOCK_AI=false
   GEMINI_API_KEY=your-key
   GEMINI_MODEL=gemini-1.5-flash
   ```
3. Restart the backend. `GET /api/health/ai` should show
   `gemini: configured + Reachable` (a real `models.get` check — a key merely
   existing is never reported as healthy).

### 3.2 OpenRouter (cloud fallback, free models only)

1. Create a key at <https://openrouter.ai/keys>.
2. Pick **free** models (ids ending in `:free`), e.g.
   `meta-llama/llama-3.3-70b-instruct:free`.
3. ```env
   MOCK_AI=false
   OPENROUTER_API_KEY=your-key
   OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
   ```

**Cost protection** (`OPENROUTER_FREE_MODELS_ONLY=true`, the default):

- only models in `OPENROUTER_ALLOWED_MODELS` (explicit allowlist), or —
  when no allowlist is set — only ids ending in `:free` are permitted;
- a configured model that is not permitted is **excluded**, OpenRouter is
  reported as *not configured* with the reason, and the manager moves to the
  next provider. A paid model is **never** picked silently;
- `OPENROUTER_MAX_SPEND` (USD) is checked via `GET /auth/key` (cached 60 s)
  before requests; when the limit is reached the provider reports quota and
  the chain falls back. `0` (default) means **zero extra API calls**.

### 3.3 Ollama (optional, local open-weight models)

1. Install: <https://ollama.com/download> (Windows/macOS/Linux).
2. Pull a small model:
   ```bash
   ollama pull qwen2.5:1.5b      # small & fast
   ollama pull llama3.2:1b       # alternative
   ```
3. ```env
   OLLAMA_ENABLED=true
   OLLAMA_MODEL=qwen2.5:1.5b
   OLLAMA_BASE_URL=http://localhost:11434
   ```
4. **In Docker**, `localhost` is the container itself — set
   `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env`.

Health check is real: Ollama reachable **and** the model installed
(otherwise the detail shows the exact `ollama pull …` command).
Ollama absent never blocks startup — the manager simply skips it.

### 3.4 Mock (development / tests / CI)

```env
MOCK_AI=true
```

- deterministic rules engine, offline, no keys, no cost;
- every response is **labelled `mock`** in the API, the topbar badge, the
  result banner and the chat messages — it can never be mistaken for real AI;
- mock is the *only* provider in the chain in this mode and is never added
  automatically when `MOCK_AI=false`.

---

## 4. Embeddings & RAG

### 4.1 Embedding backends

| `EMBEDDING_PROVIDER` | Backend | Needs | Dimension |
|---|---|---|---|
| `auto` (default) | Gemini → local → mock, first available | — | — |
| `gemini` | `GEMINI_EMBEDDING_MODEL` via google-genai | `GEMINI_API_KEY` | 768 |
| `local` | `sentence-transformers/all-MiniLM-L6-v2` | `pip install sentence-transformers` | 384 |
| `mock` | deterministic word-hash vectors | nothing | 128 |

```bash
pip install sentence-transformers   # optional, for EMBEDDING_PROVIDER=local/auto
```

**Startup warm-up:** importing sentence-transformers pulls in PyTorch
(~20 s cold) and downloads the model once (~90 MB). The backend therefore
pre-imports and pre-loads it in a **background thread at startup**
(`embedding_service.warm_up_in_background()`), and sets `USE_TF=0` so
`transformers` skips its (very slow) TensorFlow probe — we only ever use
the PyTorch backend. First analysis is fast; health reports honestly if
the package is present but broken.

**Compatibility metadata:** every stored vector records `provider`, `model`
and `dimension` (`chunk_embeddings` table). A query is only compared against
vectors with the *same* `(provider, model)`; if the embedding model changed,
chunks are re-embedded on the next retrieval instead of mixing vector spaces.

**No wasted work:** chunks store a SHA-256 content hash — re-analyzing an
unchanged document reuses every existing embedding (`embedded=0, reused=N`).
Identical texts embedded concurrently share one computation (single-flight).

### 4.2 How retrieval works

1. On analysis, `document_service` calls `rag_service.sync_document_embeddings`
   (best-effort — an embedding failure **never** fails the analysis).
2. Text is split into ~1200-char chunks with 200-char overlap at paragraph
   borders (deterministic → hashes stay stable).
3. On chat, if a document has ≥ 4 chunks, the question is embedded **once**
   and the top 4 chunks (cosine ≥ 0.05) are retrieved — scoped by
   `document_id` **and** `user_id` (two access-control layers).
4. The answer prompt receives only those excerpts, labelled `[chunk N]`, and
   the response returns `sources: [{chunk_index, excerpt, score}]` —
   only chunks that were really retrieved, never invented citations.
5. Short documents (< 4 chunks) or unavailable embeddings → the full stored
   text is used (previous behaviour), `sources: []`.

**Prompt-injection guard:** document text and excerpts are framed as
`UNTRUSTED DATA` in `services/ai/prompts.py` — instructions inside a
document are to be quoted, not obeyed.

---

## 5. Health & monitoring

`GET /api/health/ai` returns (safe fields only — no keys, no URLs with
credentials, no connection strings):

```jsonc
{
  "status": "healthy | degraded | unavailable",
  "detail": "…",
  "provider": "gemini",            // active provider
  "mode": "Google Gemini (real AI)",
  "model": "gemini-1.5-flash",
  "priority": ["gemini", "openrouter", "ollama"],
  "fallback_enabled": true,
  "timeout_seconds": 60,
  "providers": {                    // all four, always
    "gemini":     { "label", "inference", "configured", "available", "detail", "model" },
    "openrouter": { … }, "ollama": { … }, "mock": { … }
  },
  "embedding": { "provider", "model", "dimension", "status", "detail" },
  "metrics": { "requests", "success", "failed", "fallback_events", "avg_response_time_ms" },
  "recent_fallbacks": [ { "at", "operation", "from", "to", "error_category" } ]
}
```

- `available` comes from **real connectivity checks** (cached 30 s);
  `null` means "not checked yet" — an API key existing is never claimed healthy.
- `metrics` are real counters from the in-memory execution log
  (`services/ai/execution_log.py`, bounded to 200 events, reset on restart).
- The frontend shows all of this on **API Health** (provider chain cards,
  metrics tiles, recent-fallback list) and **Settings** (priority, fallback,
  embeddings).

---

## 6. Testing the providers

### 6.1 Automated (no network, no cost)

```bash
cd backend
python -m pytest -q                 # 142 tests, incl.:
python -m pytest tests/test_providers.py -q        # per-provider + error taxonomy
python -m pytest tests/test_provider_manager.py -q # chain/retry/fallback matrix
python -m pytest tests/test_embeddings.py -q       # backends, dedup, dimensions
python -m pytest tests/test_rag.py -q              # chunk/sync/retrieval/guards
```

Every network boundary is faked (SDK/HTTP mocks) — the suite never performs
a paid API call.

### 6.2 Manual per-provider check

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

1. **Mock:** `MOCK_AI=true` → `curl http://127.0.0.1:8001/api/health/ai`
   shows `mock` healthy; analyze a document → topbar says *Mock AI*.
2. **Gemini:** set `MOCK_AI=false` + `GEMINI_API_KEY`, restart →
   `/api/health/ai` shows `gemini: Reachable`; analyze → banner says
   *Google Gemini mode*.
3. **Fallback:** set an invalid `GEMINI_MODEL` (or exhaust quota) with
   `OPENROUTER_API_KEY` + a `:free` model configured → analyze again →
   toast/banner: *"Google Gemini … OpenRouter was used for this request."*
   and `/api/health/ai` shows `recent_fallbacks` with `error_category`.
4. **OpenRouter free-only:** set `OPENROUTER_MODEL=gpt-4o` with
   `OPENROUTER_FREE_MODELS_ONLY=true` → health shows OpenRouter
   *not reachable* with the free-only reason; no request is ever sent to a
   paid model.
5. **Ollama:** `OLLAMA_ENABLED=true`, `ollama pull qwen2.5:1.5b` →
   health shows *Reachable · qwen2.5:1.5b installed*; stop Ollama →
   detail says `ollama serve` and the chain falls back.
6. **Embeddings:** switch `EMBEDDING_PROVIDER` between `mock`/`local`/`gemini`
   → analyze a long document, then chat: `sources` chips appear under the
   answer; `/api/health/ai` reports the active embedding model and dimension.

---

## 7. Known limitations

- Execution metrics live in memory — they reset on backend restart and are
  per-process (fine for a single-worker dev/prod instance).
- Embeddings are stored as JSON in `document_chunks`/`chunk_embeddings`
  (works on SQLite and PostgreSQL); a vector DB (pgvector/Chroma) would be
  the next step for very large corpora.
- Retrieval is per-document (chat answers about ONE document, as before) —
  cross-document retrieval is out of scope.
- `sentence-transformers` downloads its model on first use (one-time, local).
- OpenRouter spend checking relies on `/auth/key` usage, which aggregates
  with a small delay on OpenRouter's side.

### Troubleshooting: `EMBEDDING_PROVIDER=auto/local` reports "unavailable"

A *fresh* environment resolves `sentence-transformers` correctly by itself.
On an existing machine with many pre-installed ML packages, version
conflicts can make the package present but un-importable — the health
endpoint then says so honestly instead of pretending, and `auto` falls
back to `mock`. Repair the conflict (as done on the verification machine):

```bash
pip check                        # show conflicting packages
pip install "tokenizers>=0.19,<0.20"   # transformers 4.44 requires <0.20
pip install "scipy==1.14.1"            # match a pre-existing numpy 1.26
python -c "import sentence_transformers; print('ok')"
```
