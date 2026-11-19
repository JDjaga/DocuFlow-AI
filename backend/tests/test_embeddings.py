"""Embedding service tests: backends, dimensions, compatibility, dedup."""
import threading

import pytest

from app.core.config import settings
from app.services.ai import embedding_service as es
from app.services.ai.embedding_service import (
    EXPECTED_DIMENSIONS,
    BaseEmbeddingProvider,
    EmbeddingDimensionError,
    EmbeddingResult,
    EmbeddingService,
    EmbeddingUnavailableError,
    GeminiEmbeddingProvider,
    LocalEmbeddingProvider,
    MockEmbeddingProvider,
    cosine_similarity,
    resolve_embedding_provider,
)


# ======================================================================
# Mock backend (deterministic, offline)
# ======================================================================
def test_mock_embeddings_are_deterministic_and_normalized():
    provider = MockEmbeddingProvider()
    first = provider.embed_batch(["hello world", "deadline 2026"])[0]
    second = provider.embed_batch(["hello world", "deadline 2026"])[0]

    assert first == second  # deterministic across calls
    assert len(first) == provider.DIMENSION == EXPECTED_DIMENSIONS["mock-hash-v1"]
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-6  # L2 normalized


def test_mock_embeddings_reflect_word_overlap():
    provider = MockEmbeddingProvider()
    shared = "urgent deadline proposal review"
    a, b, c = provider.embed_batch([shared, f"{shared} extra words", "totally unrelated text"])

    overlap_score = cosine_similarity(a, b)
    unrelated_score = cosine_similarity(a, c)
    assert overlap_score > unrelated_score
    assert overlap_score > 0.3  # shared words must land in same dimensions


# ======================================================================
# Service behaviour
# ======================================================================
class CountingBackend(BaseEmbeddingProvider):
    """Fake backend that records every batch it receives."""

    name = "local"
    MODEL_ID = "fake-model"

    def __init__(self, dimension=4, break_dims=False):
        self.calls = []
        self.dimension = dimension
        self.break_dims = break_dims

    @property
    def model(self):
        return self.MODEL_ID

    def embed_batch(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for index, _ in enumerate(texts):
            if self.break_dims and index % 2 == 1:
                vectors.append([0.0] * (self.dimension + 1))
            else:
                vectors.append([1.0] * self.dimension)
        return vectors


def test_service_embeds_and_records_metadata():
    backend = CountingBackend()
    service = EmbeddingService(backend)

    result = service.embed_text("some text")

    assert isinstance(result, EmbeddingResult)
    assert result.provider == "local"
    assert result.model == "fake-model"
    assert result.dimension == 4
    assert result.signature == ("local", "fake-model")


def test_duplicate_texts_are_embedded_once_per_call():
    backend = CountingBackend()
    service = EmbeddingService(backend)

    results = service.embed_documents(["same", "same", "other"])

    assert len(results) == 3
    assert backend.calls == [["same", "other"]]  # duplicates removed
    assert results[0].vector == results[1].vector


def test_query_and_document_embeddings_share_model_space():
    service = EmbeddingService(CountingBackend())
    assert service.embed_query("q").signature == service.embed_documents(["d"])[0].signature


def test_dimension_mismatch_is_rejected():
    service = EmbeddingService(CountingBackend(break_dims=True))
    with pytest.raises(EmbeddingDimensionError):
        service.embed_documents(["a", "b"])


def test_backend_failure_becomes_embedding_error():
    class FailingBackend(BaseEmbeddingProvider):
        name = "gemini"
        model = "text-embedding-004"

        def embed_batch(self, texts):
            raise EmbeddingUnavailableError("Gemini embedding quota/rate limit was reached.")

    service = EmbeddingService(FailingBackend())
    with pytest.raises(EmbeddingUnavailableError):
        service.embed_text("x")


def test_single_flight_shares_concurrent_computation():
    """Two threads embedding the same text hit the backend once."""

    class SlowBackend(CountingBackend):
        def embed_batch(self, texts):
            import time

            time.sleep(0.15)
            return super().embed_batch(texts)

    backend = SlowBackend()
    service = EmbeddingService(backend)
    results = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.extend(service.embed_documents(["shared text"]))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert results[0].vector == results[1].vector
    # One backend call for two concurrent identical requests.
    assert sum(len(batch) for batch in backend.calls) == 1


# ======================================================================
# Resolution / configuration
# ======================================================================
def test_resolve_explicit_providers(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "mock")
    assert isinstance(resolve_embedding_provider(settings), MockEmbeddingProvider)

    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "gemini")
    assert isinstance(resolve_embedding_provider(settings), GeminiEmbeddingProvider)

    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local")
    assert isinstance(resolve_embedding_provider(settings), LocalEmbeddingProvider)


def test_resolve_auto_prefers_gemini_then_local_then_mock(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "auto")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "key-present")
    assert isinstance(resolve_embedding_provider(settings), GeminiEmbeddingProvider)

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(
        "app.services.ai.embedding_service.local_embeddings_available", lambda: True
    )
    assert isinstance(resolve_embedding_provider(settings), LocalEmbeddingProvider)

    monkeypatch.setattr(
        "app.services.ai.embedding_service.local_embeddings_available", lambda: False
    )
    assert isinstance(resolve_embedding_provider(settings), MockEmbeddingProvider)


def test_resolve_rejects_unknown_provider():
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "pinecone")
        with pytest.raises(ValueError):
            resolve_embedding_provider(settings)
    finally:
        monkeypatch.undo()


def test_expected_dimensions_are_reported_honestly():
    assert EXPECTED_DIMENSIONS["sentence-transformers/all-MiniLM-L6-v2"] == 384
    assert EXPECTED_DIMENSIONS["text-embedding-004"] == 768
    service = EmbeddingService(CountingBackend())  # model "fake-model"
    assert service.expected_dimension() is None  # unknown -> do not invent


# ======================================================================
# Gemini embeddings (faked SDK)
# ======================================================================
def test_gemini_embedding_success_and_error_mapping(monkeypatch):
    from types import SimpleNamespace

    provider = GeminiEmbeddingProvider()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    class FakeModels:
        def embed_content(self, **kwargs):
            return SimpleNamespace(embedding=[0.1, 0.2, 0.3])

    monkeypatch.setattr(
        provider, "_get_client", lambda: SimpleNamespace(models=FakeModels())
    )
    vectors = provider.embed_batch(["hello"])
    assert vectors == [[0.1, 0.2, 0.3]]

    class ApiError(Exception):
        def __init__(self, code, message="x"):
            super().__init__(message)
            self.code = code

    class FailingModels:
        def embed_content(self, **kwargs):
            raise ApiError(429, "quota exceeded")

    monkeypatch.setattr(
        provider, "_get_client", lambda: SimpleNamespace(models=FailingModels())
    )
    with pytest.raises(es.EmbeddingUnavailableError) as error:
        provider.embed_batch(["hello"])
    assert "quota" in str(error.value).lower()


def test_gemini_embedding_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    with pytest.raises(es.EmbeddingUnavailableError):
        GeminiEmbeddingProvider().embed_batch(["x"])


# ======================================================================
# Cosine similarity
# ======================================================================
def test_cosine_similarity_basics():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0  # never mix dims
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
