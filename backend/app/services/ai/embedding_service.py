"""Independent embedding provider system for RAG / semantic retrieval.

WHAT THIS FILE DOES
    Generation providers and embedding providers are completely
    independent: embeddings come from ONE configured source
    (EMBEDDING_PROVIDER = gemini | local | mock | auto), regardless of
    which provider answers questions.

    Every EmbeddingResult records provider, model and dimension, and
    every stored vector must carry that metadata (see rag_service) so
    incompatible vectors are never compared or mixed.

SUPPORTED EMBEDDING BACKENDS
    Gemini  - GEMINI_EMBEDDING_MODEL via the google-genai SDK
    Local   - sentence-transformers/all-MiniLM-L6-v2 through the
              optional sentence-transformers package (no API key)
    Mock    - deterministic hash-based vectors for dev/tests/CI
              (clearly labelled, never mixed with real vectors)

DUPLICATE PROTECTION
    Identical texts embedded concurrently share one computation
    (single-flight), and unchanged document chunks are reused at the
    database level by rag_service via content hashes.

HOW IT CONNECTS
    rag_service -> get_embedding_service().embed_query()/embed_documents()
    GET /api/health/ai -> service status (provider, model, dimension)
"""
from __future__ import annotations

import hashlib
import importlib.util
import logging
import math
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

# sentence-transformers pulls in `transformers`, which probes for a local
# TensorFlow install at import time. TensorFlow's import alone can take a
# minute on Windows, and this service only ever uses the PyTorch backend -
# so disable the TF probe (setdefault: an explicit USE_TF=1 is respected).
# MUST happen before transformers/sentence_transformers is first imported.
os.environ.setdefault("USE_TF", "0")

from app.core.config import settings

logger = logging.getLogger("docuflow.ai")

#: dimensions we can state confidently without an API call
EXPECTED_DIMENSIONS: dict[str, int] = {
    "text-embedding-004": 768,
    "text-embedding-001": 768,
    "embedding-001": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "mock-hash-v1": 128,
}

_SINGLE_FLIGHT_TTL = 300.0  # seconds to keep a shared result available

#: cached result of "can sentence-transformers really be imported?"
_LOCAL_AVAILABLE: bool | None = None


class EmbeddingError(Exception):
    """Embedding failures never trigger generation-provider fallback."""

    category = "embedding_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.safe_message = message


class EmbeddingUnavailableError(EmbeddingError):
    """The configured embedding backend cannot serve requests."""

    category = "embedding_unavailable"


class EmbeddingDimensionError(EmbeddingError):
    """Vectors of different lengths were produced - never store these."""

    category = "dimension_mismatch"


@dataclass(frozen=True)
class EmbeddingResult:
    """One vector with its full compatibility metadata."""

    vector: list[float]
    provider: str
    model: str
    dimension: int

    @property
    def signature(self) -> tuple[str, str]:
        """(provider, model) - two vectors may only meet if equal."""
        return (self.provider, self.model)


# ----------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------
class BaseEmbeddingProvider(ABC):
    """One embedding backend."""

    name: str = "provider"

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier recorded with every vector."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text (same order)."""


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini embeddings (cloud, needs GEMINI_API_KEY)."""

    name = "gemini"

    @property
    def model(self) -> str:
        return settings.GEMINI_EMBEDDING_MODEL

    def _get_client(self):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise EmbeddingUnavailableError(
                "The 'google-genai' package is not installed for Gemini embeddings."
            ) from exc
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={"timeout": settings.AI_REQUEST_TIMEOUT * 1000},
        )

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not settings.GEMINI_API_KEY.strip():
            raise EmbeddingUnavailableError("GEMINI_API_KEY is not configured for Gemini embeddings.")

        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise EmbeddingUnavailableError(
                "The 'google-genai' package is not installed for Gemini embeddings."
            ) from exc

        client = self._get_client()

        try:
            if len(texts) == 1:
                response = client.models.embed_content(model=self.model, contents=texts[0])
                vectors = [list(response.embedding)]
            else:
                try:
                    request = types.BatchEmbedContentsRequest(
                        model=self.model,
                        requests=[
                            types.EmbedContentRequest(model=self.model, contents=text)
                            for text in texts
                        ],
                    )
                    response = client.models.batch_embed_contents(request)
                    vectors = [list(item.embedding) for item in response.embeddings]
                except (AttributeError, TypeError, ValueError):
                    # Older SDK without batch support: embed one by one.
                    vectors = []
                    for text in texts:
                        single = client.models.embed_content(
                            model=self.model, contents=text
                        )
                        vectors.append(list(single.embedding))
        except EmbeddingError:
            raise
        except Exception as exc:  # noqa: BLE001 - SDK exposes several error types
            status = getattr(exc, "code", None)
            message = str(exc).lower()
            if status == 429 or "quota" in message or "rate" in message:
                raise EmbeddingUnavailableError(
                    "Gemini embedding quota/rate limit was reached."
                ) from exc
            if status in (400, 401, 403, 404):
                raise EmbeddingUnavailableError(
                    "Gemini rejected the embedding request (check key/model)."
                ) from exc
            if "timeout" in message or "timed out" in message:
                raise EmbeddingUnavailableError("Gemini embedding request timed out.") from exc
            raise EmbeddingUnavailableError("Gemini embeddings are unavailable.") from exc

        return [[float(value) for value in vector] for vector in vectors]


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Hugging Face model through sentence-transformers (offline, optional)."""

    name = "local"
    _instance: Any = None
    _instance_lock = threading.Lock()

    @property
    def model(self) -> str:
        return settings.LOCAL_EMBEDDING_MODEL

    def _get_model(self) -> Any:
        with LocalEmbeddingProvider._instance_lock:
            if LocalEmbeddingProvider._instance is not None:
                return LocalEmbeddingProvider._instance
            if importlib.util.find_spec("sentence_transformers") is None:
                raise EmbeddingUnavailableError(
                    "sentence-transformers is not installed. "
                    "Run: pip install sentence-transformers"
                )
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as exc:  # installed but broken (dep conflict)
                raise EmbeddingUnavailableError(
                    "sentence-transformers is installed but cannot be imported "
                    f"({exc}). Try: pip install -U sentence-transformers"
                ) from exc
            try:
                LocalEmbeddingProvider._instance = SentenceTransformer(self.model)
            except Exception as exc:  # bad model id / no network for first download
                raise EmbeddingUnavailableError(
                    f"Could not load local embedding model '{self.model}'. "
                    "Check the model id and network access."
                ) from exc
            return LocalEmbeddingProvider._instance

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        try:
            vectors = model.encode(texts)
        except Exception as exc:  # noqa: BLE001 - library-specific errors
            raise EmbeddingUnavailableError(
                f"Local embedding model '{self.model}' failed to encode the text."
            ) from exc
        return [[float(value) for value in vector] for vector in vectors]


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic offline vectors for dev/test (never mixed with real ones)."""

    name = "mock"
    MODEL_ID = "mock-hash-v1"
    DIMENSION = 128

    @property
    def model(self) -> str:
        return self.MODEL_ID

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.DIMENSION
            # Position depends ONLY on the word, so the same word lands in
            # the same dimension in every text - cosine similarity then
            # reflects real word overlap (good enough for deterministic dev).
            for word in text.lower().split():
                digest = hashlib.md5(word.encode("utf-8")).hexdigest()
                position = int(digest[:8], 16) % self.DIMENSION
                vector[position] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


# ----------------------------------------------------------------------
# Resolution + service
# ----------------------------------------------------------------------
def local_embeddings_available() -> bool:
    """True when sentence-transformers is really IMPORTABLE.

    A plain find_spec() check is not enough: the package can be present
    while its dependencies are broken (version conflicts), which would
    make "auto" pick a backend that then fails on every request. The
    result is cached per process - installing packages requires a
    restart anyway.
    """
    global _LOCAL_AVAILABLE
    if _LOCAL_AVAILABLE is not None:
        return _LOCAL_AVAILABLE
    try:
        import sentence_transformers  # noqa: F401 - the import IS the check
    except Exception:  # noqa: BLE001 - any import failure = unavailable
        _LOCAL_AVAILABLE = False
        logger.warning(
            "sentence-transformers is present but cannot be imported "
            "(broken dependencies?). EMBEDDING_PROVIDER=auto will skip it. "
            "Run: pip install sentence-transformers",
        )
    else:
        _LOCAL_AVAILABLE = True
    return _LOCAL_AVAILABLE


def resolve_embedding_provider(cfg: Any | None = None) -> BaseEmbeddingProvider:
    """Turn EMBEDDING_PROVIDER into a concrete backend.

    "auto" prefers Gemini (when a key exists), then the local model if
    installed, and finally the deterministic mock - so the default dev
    experience works with zero keys and zero extra packages.
    """
    cfg = cfg or settings
    choice = (cfg.EMBEDDING_PROVIDER or "auto").strip().lower()

    if choice == "gemini":
        return GeminiEmbeddingProvider()
    if choice == "local":
        return LocalEmbeddingProvider()
    if choice == "mock":
        return MockEmbeddingProvider()
    if choice == "auto":
        if cfg.GEMINI_API_KEY.strip():
            return GeminiEmbeddingProvider()
        if local_embeddings_available():
            return LocalEmbeddingProvider()
        return MockEmbeddingProvider()
    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER '{choice}'. Valid values: auto, gemini, local, mock."
    )


class EmbeddingService:
    """Embeds text with the configured backend and guards compatibility."""

    def __init__(self, provider: BaseEmbeddingProvider) -> None:
        self.provider = provider
        self._lock = threading.Lock()
        self._inflight: dict[str, threading.Event] = {}
        self._computed: dict[str, tuple[float, EmbeddingResult]] = {}

    # --- Identity --------------------------------------------------------
    @property
    def provider_name(self) -> str:
        return self.provider.name

    @property
    def model_name(self) -> str:
        return self.provider.model

    @property
    def signature(self) -> tuple[str, str]:
        return (self.provider.name, self.provider.model)

    def expected_dimension(self) -> int | None:
        """Dimension we can state confidently, or None until first use."""
        return EXPECTED_DIMENSIONS.get(self.provider.model)

    # --- Embedding -------------------------------------------------------
    def embed_text(self, text: str) -> EmbeddingResult:
        return self.embed_documents([text])[0]

    def embed_query(self, text: str) -> EmbeddingResult:
        """Queries MUST use the same provider/model as stored documents."""
        return self.embed_text(text)

    def embed_documents(self, texts: list[str]) -> list[EmbeddingResult]:
        """Embed texts with single-flight duplicate protection.

        Raises EmbeddingError subclasses on backend failures or when a
        backend returns inconsistent vector lengths.
        """
        if not texts:
            return []

        # 1) Claim unique texts or wait for an in-flight computation.
        results: dict[str, EmbeddingResult] = {}
        to_compute: list[str] = []
        waits: list[threading.Event] = []
        now = time.monotonic()

        with self._lock:
            # Sweep shared results older than the TTL.
            stale = [
                key
                for key, (ts, _) in self._computed.items()
                if now - ts > _SINGLE_FLIGHT_TTL
            ]
            for key in stale:
                self._computed.pop(key, None)

            seen: set[str] = set()
            for text in texts:
                if text in seen:
                    continue
                seen.add(text)
                key = self._key(text)
                event = self._inflight.get(key)
                if event is not None:
                    waits.append(event)
                else:
                    self._inflight[key] = threading.Event()
                    to_compute.append(text)

        # 2) Wait for computations owned by other requests.
        for event in waits:
            event.wait(timeout=settings.AI_REQUEST_TIMEOUT)

        # 3) Compute the texts we own (batched).
        if to_compute:
            try:
                vectors = self._raw_embed(to_compute)
            except Exception:
                # Wake any waiters so they fail fast instead of hanging.
                with self._lock:
                    for text in to_compute:
                        event = self._inflight.pop(self._key(text), None)
                        if event is not None:
                            event.set()
                raise
            computed_at = time.monotonic()
            with self._lock:
                for text, vector in zip(to_compute, vectors):
                    key = self._key(text)
                    result = EmbeddingResult(
                        vector=vector,
                        provider=self.provider.name,
                        model=self.provider.model,
                        dimension=len(vector),
                    )
                    self._computed[key] = (computed_at, result)
                    results[key] = result
                    event = self._inflight.pop(key, None)
                    if event is not None:
                        event.set()

        # 4) Collect shared results for texts we waited on.
        with self._lock:
            for text in texts:
                key = self._key(text)
                if key in results:
                    continue
                shared = self._computed.get(key)
                if shared is None:
                    raise EmbeddingUnavailableError(
                        "The embedding computation did not complete."
                    )
                results[key] = shared[1]

        return [results[self._key(text)] for text in texts]

    def _raw_embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.provider.embed_batch(texts)
        if len(vectors) != len(texts):
            raise EmbeddingUnavailableError(
                f"{self.provider.name} returned {len(vectors)} vectors for {len(texts)} texts."
            )
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise EmbeddingDimensionError(
                "The embedding backend returned vectors of different lengths."
            )
        if 0 in dimensions:
            raise EmbeddingDimensionError("The embedding backend returned an empty vector.")
        return vectors

    @staticmethod
    def _key(text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return digest


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 for zero vectors or mismatch."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ----------------------------------------------------------------------
# Process-wide singleton
# ----------------------------------------------------------------------
from functools import lru_cache  # noqa: E402 - placed here for readability


@lru_cache(maxsize=1)
def _build_embedding_service() -> EmbeddingService:
    return EmbeddingService(resolve_embedding_provider(settings))


def get_embedding_service() -> EmbeddingService:
    """Cached service built from the current settings."""
    return _build_embedding_service()


def reset_embedding_service() -> None:
    """Drop the cached service (tests change EMBEDDING_PROVIDER)."""
    _build_embedding_service.cache_clear()
    global _LOCAL_AVAILABLE
    _LOCAL_AVAILABLE = None


def warm_up_in_background() -> None:
    """Pre-import and pre-load the local embedding model off the hot path.

    The first `sentence-transformers` import pulls in PyTorch (~20s on a
    cold start) and the model downloads once (~90 MB). Doing that in a
    daemon thread at startup keeps the first user request fast. Runs only
    for EMBEDDING_PROVIDER=auto/local; failures are logged, never raised.
    """

    def _warm() -> None:
        try:
            provider = resolve_embedding_provider(settings)
            if provider.name != "local":
                return
            provider.embed_batch(["warm-up"])  # import + model load + encode
            logger.info("Local embedding model ready (%s).", provider.model)
        except Exception as exc:  # noqa: BLE001 - warm-up must never crash
            logger.warning("Embedding warm-up skipped: %s", exc)

    threading.Thread(target=_warm, daemon=True, name="embedding-warmup").start()
