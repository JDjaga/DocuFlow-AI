"""Application configuration.

WHAT THIS FILE DOES
    Reads every setting the backend needs from environment variables
    (optionally loaded from backend/.env) and exposes them through one
    object: `settings`.

WHY IT EXISTS
    No secret, port or key is ever written directly inside business code.
    Everything configurable lives here, so changing environment =
    changing behaviour without touching the source.

HOW IT CONNECTS
    security.py           -> SECRET_KEY, ALGORITHM, token lifetime
    connection.py         -> DATABASE_URL
    services/ai/*         -> provider priority, keys, models, retries
    services/ai/embedding -> EMBEDDING_PROVIDER, LOCAL_EMBEDDING_MODEL
    main.py               -> CORS_ORIGINS, startup validation

INTERVIEW NOTE
    "All configuration is injected through pydantic-settings, so secrets
     stay out of the codebase and the same image can run in dev and prod."
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Path(...).parents[2] = backend/   (config.py -> core -> app -> backend)
BACKEND_DIR = Path(__file__).resolve().parents[2]

KNOWN_AI_PROVIDERS = ("gemini", "openrouter", "ollama", "mock")
KNOWN_EMBEDDING_PROVIDERS = ("auto", "gemini", "local", "mock")


class Settings(BaseSettings):
    """Typed application settings. Values come from env vars or .env."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",  # unknown env vars are ignored instead of crashing
    )

    # --- Application -------------------------------------------------
    APP_NAME: str = "DocuFlow AI"
    APP_VERSION: str = "1.0.0"

    # --- Security ----------------------------------------------------
    SECRET_KEY: str = "dev-secret-change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # --- Database ----------------------------------------------------
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'docuflow.db'}"

    # --- AI mode -----------------------------------------------------
    # true  -> deterministic Mock engine only (dev / tests / CI, no keys)
    # false -> real providers in AI_PROVIDER_PRIORITY order
    MOCK_AI: bool = True
    MAX_INPUT_CHARS: int = 40000

    # --- AI provider priority & reliability --------------------------
    # Order matters: first configured provider is primary, the rest are
    # automatic fallbacks (only when AI_FALLBACK_ENABLED=true).
    AI_PROVIDER_PRIORITY: str = "gemini,openrouter,ollama"
    AI_MAX_RETRIES: int = 2          # per provider, exponential backoff
    AI_REQUEST_TIMEOUT: int = 60     # seconds, per provider attempt
    AI_FALLBACK_ENABLED: bool = True

    # --- Google Gemini (primary cloud AI) ----------------------------
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # --- OpenRouter (cloud fallback) ---------------------------------
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = ""
    OPENROUTER_FALLBACK_MODELS: str = ""          # comma-separated list
    OPENROUTER_FREE_MODELS_ONLY: bool = True      # never pick paid models
    OPENROUTER_ALLOWED_MODELS: str = ""           # free-model allowlist
    OPENROUTER_MAX_SPEND: float = 0.0             # 0 = no limit

    # --- Ollama (optional local inference) ---------------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = ""
    OLLAMA_ENABLED: bool = False

    # --- Embeddings (independent from generation providers) ----------
    EMBEDDING_PROVIDER: str = "auto"   # auto | gemini | local | mock
    LOCAL_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Uploads -----------------------------------------------------
    MAX_FILE_SIZE_MB: int = 10

    # --- CORS --------------------------------------------------------
    # Stored as a plain string so the .env file stays easy to read.
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
    )

    # ---- Derived helpers -------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        """CORS_ORIGINS turned into a real Python list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def ai_priority_list(self) -> list[str]:
        """AI_PROVIDER_PRIORITY as a clean list of lower-case names."""
        return [
            part.strip().lower()
            for part in self.AI_PROVIDER_PRIORITY.split(",")
            if part.strip()
        ]

    @property
    def ai_provider(self) -> str:
        """Short label for the startup banner / health endpoint.

        Reports the first CONFIGURED provider (never claims a provider
        is active when its key or model is missing).
        """
        if self.MOCK_AI:
            return "mock"
        for name in self.ai_priority_list:
            if name == "mock":
                continue  # never a silent production fallback
            if name == "gemini" and self.GEMINI_API_KEY.strip():
                return "gemini"
            if name == "openrouter" and self.OPENROUTER_API_KEY.strip():
                return "openrouter"
            if (
                name == "ollama"
                and self.OLLAMA_ENABLED
                and self.OLLAMA_MODEL.strip()
            ):
                return "ollama"
        return "none"

    # ---- Startup validation ----------------------------------------
    def validate_ai_settings(self) -> list[str]:
        """Validate AI configuration at startup.

        Raises ValueError for malformed values (fail fast - the app must
        not start with a config that can never work). Returns human
        warnings for incomplete-but-valid setups (missing keys), which
        are logged instead of crashing the app.
        """
        warnings: list[str] = []

        # --- must be valid -------------------------------------------
        names = self.ai_priority_list
        if not names:
            raise ValueError(
                "AI_PROVIDER_PRIORITY must list at least one provider "
                "(e.g. gemini,openrouter,ollama)."
            )
        unknown = [name for name in names if name not in KNOWN_AI_PROVIDERS]
        if unknown:
            raise ValueError(
                f"AI_PROVIDER_PRIORITY contains unknown providers: "
                f"{', '.join(unknown)}. Valid values: "
                f"{', '.join(KNOWN_AI_PROVIDERS)}."
            )
        if self.AI_MAX_RETRIES < 0:
            raise ValueError("AI_MAX_RETRIES must be 0 or greater.")
        if self.AI_REQUEST_TIMEOUT <= 0:
            raise ValueError("AI_REQUEST_TIMEOUT must be greater than 0.")
        if self.OPENROUTER_MAX_SPEND < 0:
            raise ValueError("OPENROUTER_MAX_SPEND must be 0 or greater.")
        embedding = self.EMBEDDING_PROVIDER.strip().lower()
        if embedding not in KNOWN_EMBEDDING_PROVIDERS:
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER '{self.EMBEDDING_PROVIDER}'. "
                f"Valid values: {', '.join(KNOWN_EMBEDDING_PROVIDERS)}."
            )

        # --- warnings (valid but likely incomplete) -------------------
        if not self.MOCK_AI:
            cloud_ready = bool(
                self.GEMINI_API_KEY.strip()
                or self.OPENROUTER_API_KEY.strip()
                or (self.OLLAMA_ENABLED and self.OLLAMA_MODEL.strip())
            )
            if not cloud_ready:
                warnings.append(
                    "MOCK_AI=false but no AI provider is configured: set "
                    "GEMINI_API_KEY, OPENROUTER_API_KEY or OLLAMA_ENABLED=true. "
                    "AI requests will fail until one is added."
                )

        if (
            not self.MOCK_AI
            and self.OPENROUTER_FREE_MODELS_ONLY
            and self.OPENROUTER_API_KEY.strip()
        ):
            candidates = [
                model.strip()
                for model in [
                    self.OPENROUTER_MODEL,
                    *self.OPENROUTER_FALLBACK_MODELS.split(","),
                ]
                if model.strip()
            ]
            allowed = {
                model.strip()
                for model in self.OPENROUTER_ALLOWED_MODELS.split(",")
                if model.strip()
            }
            permitted = (
                [model for model in candidates if model in allowed]
                if allowed
                else [model for model in candidates if model.endswith(":free")]
            )
            if candidates and not permitted:
                warnings.append(
                    "OPENROUTER_FREE_MODELS_ONLY excludes every configured "
                    "OpenRouter model - add free models to "
                    "OPENROUTER_ALLOWED_MODELS or use ids ending in ':free'."
                )

        return warnings


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the settings object is built only once."""
    return Settings()


settings = get_settings()
