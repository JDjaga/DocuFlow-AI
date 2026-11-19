"""Provider unit tests: Gemini, OpenRouter, Ollama, Mock + validation.

Every network boundary is faked - no API keys, no cost, no network.
"""
import json
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.ai.ai_exceptions import (
    ConnectionFailedError,
    InvalidInputError,
    InvalidResponseError,
    ModelNotFoundError,
    ProviderAuthError,
    ProviderServerError,
    ProviderTimeoutError,
    QuotaExceededError,
    RateLimitError,
    UnexpectedProviderError,
    classify_status_code,
)
from app.services.ai.gemini_provider import GeminiProvider, _translate_gemini_error
from app.services.ai.mock_provider import MockProvider
from app.services.ai.openrouter_provider import OpenRouterProvider, permitted_models
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.response_validator import (
    extract_json_object,
    validate_answer,
    validate_analysis,
)


# ======================================================================
# Error classification (shared)
# ======================================================================
def test_status_classification_maps_http_codes():
    assert isinstance(classify_status_code(429, "slow down"), RateLimitError)
    assert isinstance(classify_status_code(429, "quota exceeded"), QuotaExceededError)
    assert isinstance(classify_status_code(401), ProviderAuthError)
    assert isinstance(classify_status_code(403), ProviderAuthError)
    assert isinstance(classify_status_code(500), ProviderServerError)
    assert isinstance(classify_status_code(400, "bad"), InvalidInputError)
    assert isinstance(classify_status_code(404, "model not found"), ModelNotFoundError)


# ======================================================================
# Response validation
# ======================================================================
def test_extract_json_handles_fences_and_commentary():
    payload = {"summary": "s"}
    assert extract_json_object(payload) == payload
    assert extract_json_object(f"```json\n{json.dumps(payload)}\n```") == payload
    assert extract_json_object(f"Sure! Here it is: {json.dumps(payload)} done.") == payload


def test_extract_json_rejects_arrays_and_garbage():
    with pytest.raises(InvalidResponseError):
        extract_json_object("[1,2]")
    with pytest.raises(InvalidResponseError):
        extract_json_object("no json here")
    with pytest.raises(InvalidResponseError):
        extract_json_object("")


def test_validate_analysis_wraps_schema_failures():
    with pytest.raises(InvalidResponseError):
        validate_analysis({"summary": "", "category": "X", "priority": "Impossible"})
    with pytest.raises(InvalidResponseError):
        validate_analysis(["not", "an", "object"])


def test_validate_answer_bounds_length():
    assert validate_answer("  hello  ") == "hello"
    with pytest.raises(InvalidResponseError):
        validate_answer("")
    assert len(validate_answer("x" * 20000)) == 8000


# ======================================================================
# Mock provider
# ======================================================================
def test_mock_provider_is_deterministic_and_labelled():
    provider = MockProvider()
    assert provider.is_configured() is True
    assert provider.current_model() == "-"
    assert provider.inference == "simulated"

    first = provider.answer_question("The deadline is 2026-12-01.", "deadline?")
    second = provider.answer_question("The deadline is 2026-12-01.", "deadline?")
    assert first.data == second.data  # deterministic
    assert first.provider == "mock"

    generated = provider.generate_text("anything")
    assert "simulated" in generated.data.lower()  # never claims real inference
    ok, detail = provider.check_connection()
    assert ok is True
    assert "no external api" in detail.lower()


def test_mock_analyze_returns_validated_analysis():
    provider = MockProvider()
    result = provider.analyze_document("Please review this urgent proposal by 2026-12-01.")
    assert result.provider == "mock"
    assert result.data.priority in ("High", "Medium", "Low")


# ======================================================================
# Gemini provider
# ======================================================================
class _FakeGeminiClient:
    """Stands in for genai.Client - captures generate_content calls."""

    def __init__(self, text="", error=None, usage=None):
        self.text = text
        self.error = error
        self.usage = usage
        self.calls = []
        self.models = SimpleNamespace(
            generate_content=self._generate_content,
            get=lambda **kwargs: SimpleNamespace(name="model"),
        )

    def _generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            text=self.text,
            usage_metadata=SimpleNamespace(
                prompt_token_count=(self.usage or {}).get("input_tokens"),
                candidates_token_count=(self.usage or {}).get("output_tokens"),
            )
        )


@pytest.fixture()
def gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test-model")


def test_gemini_successful_generation(monkeypatch, gemini_key):
    provider = GeminiProvider()
    client = _FakeGeminiClient(text="hello from gemini")
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    result = provider.generate_text("hi")

    assert result.provider == "gemini"
    assert result.model == "gemini-test-model"
    assert result.data == "hello from gemini"
    assert client.calls, "generate_content must be called"


def test_gemini_structured_output_and_json_mode(monkeypatch, gemini_key):
    provider = GeminiProvider()
    client = _FakeGeminiClient(text='```json\n{"summary":"s"}\n```')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    result = provider.generate_structured("analyze")

    assert result.data == {"summary": "s"}
    config = client.calls[0]["config"]
    assert config.response_mime_type == "application/json"


def test_gemini_empty_response_is_invalid(monkeypatch, gemini_key):
    provider = GeminiProvider()
    monkeypatch.setattr(provider, "_get_client", lambda: _FakeGeminiClient(text="  "))

    with pytest.raises(InvalidResponseError):
        provider.generate_text("hi")


def test_gemini_quota_and_rate_limit_errors(monkeypatch, gemini_key):
    provider = GeminiProvider()

    class ApiError(Exception):
        def __init__(self, code, message):
            super().__init__(message)
            self.code = code

    monkeypatch.setattr(
        provider, "_get_client",
        lambda: _FakeGeminiClient(error=ApiError(429, "quota exhausted for today")),
    )
    with pytest.raises(QuotaExceededError):
        provider.generate_text("hi")

    monkeypatch.setattr(
        provider, "_get_client",
        lambda: _FakeGeminiClient(error=ApiError(429, "too many requests per minute")),
    )
    with pytest.raises(RateLimitError):
        provider.generate_text("hi")


def test_gemini_timeout_and_auth_errors_are_classified():
    class ApiError(Exception):
        def __init__(self, code, message="x"):
            super().__init__(message)
            self.code = code

    assert isinstance(
        _translate_gemini_error(ApiError(401, "bad key")), ProviderAuthError
    )
    assert isinstance(
        _translate_gemini_error(ApiError(500)), ProviderServerError
    )
    assert isinstance(
        _translate_gemini_error(ApiError(400)), InvalidInputError
    )
    assert isinstance(
        _translate_gemini_error(ApiError(404)), ModelNotFoundError
    )
    assert isinstance(
        _translate_gemini_error(Exception("Request timed out")), ProviderTimeoutError
    )
    assert isinstance(
        _translate_gemini_error(Exception("connection reset by peer")),
        ConnectionFailedError,
    )
    assert isinstance(
        _translate_gemini_error(Exception("mystery")), UnexpectedProviderError
    )


def test_gemini_check_connection_without_key():
    provider = GeminiProvider()
    ok, detail = provider.check_connection()
    assert ok is False
    assert "GEMINI_API_KEY" in detail


def test_gemini_check_connection_with_key(monkeypatch, gemini_key):
    provider = GeminiProvider()
    monkeypatch.setattr(provider, "_get_client", lambda: _FakeGeminiClient())
    ok, detail = provider.check_connection()
    assert ok is True
    assert "reachable" in detail.lower()


# ======================================================================
# OpenRouter provider
# ======================================================================
class _FakeHTTPResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _chat_payload(content="hello", usage=None):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": usage or {"prompt_tokens": 7, "completion_tokens": 3},
    }


@pytest.fixture()
def openrouter_env(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "or-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "vendor/free-model:free")
    monkeypatch.setattr(settings, "OPENROUTER_FALLBACK_MODELS", "")
    monkeypatch.setattr(settings, "OPENROUTER_FREE_MODELS_ONLY", True)
    monkeypatch.setattr(settings, "OPENROUTER_ALLOWED_MODELS", "")
    monkeypatch.setattr(settings, "OPENROUTER_MAX_SPEND", 0.0)


def test_openrouter_success(monkeypatch, openrouter_env):
    provider = OpenRouterProvider()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _FakeHTTPResponse(payload=_chat_payload("hi there"))

    monkeypatch.setattr("app.services.ai.openrouter_provider.httpx.post", fake_post)

    result = provider.generate_text("prompt")

    assert result.provider == "openrouter"
    assert result.model == "vendor/free-model:free"
    assert result.data == "hi there"
    assert result.usage == {"input_tokens": 7, "output_tokens": 3}
    assert captured["url"].endswith("/chat/completions")
    assert "response_format" not in captured["json"]  # plain text request


def test_openrouter_structured_uses_json_mode(monkeypatch, openrouter_env):
    provider = OpenRouterProvider()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _FakeHTTPResponse(payload=_chat_payload('{"summary":"s"}'))

    monkeypatch.setattr("app.services.ai.openrouter_provider.httpx.post", fake_post)

    result = provider.generate_structured("analyze")

    assert result.data == {"summary": "s"}
    assert captured["json"]["response_format"] == {"type": "json_object"}


def test_openrouter_model_fallback_list(monkeypatch, openrouter_env):
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "missing:free")
    monkeypatch.setattr(settings, "OPENROUTER_FALLBACK_MODELS", "backup:free")
    provider = OpenRouterProvider()
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs["json"]["model"])
        if kwargs["json"]["model"] == "missing:free":
            return _FakeHTTPResponse(404, text='{"error":{"message":"Model not found"}}')
        return _FakeHTTPResponse(payload=_chat_payload("served by backup"))

    monkeypatch.setattr("app.services.ai.openrouter_provider.httpx.post", fake_post)

    result = provider.generate_text("hi")

    assert calls == ["missing:free", "backup:free"]
    assert result.model == "backup:free"
    assert result.data == "served by backup"


def test_openrouter_free_only_excludes_paid_models(monkeypatch, openrouter_env):
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "gpt-4o")
    monkeypatch.setattr(settings, "OPENROUTER_FALLBACK_MODELS", "claude-x")

    assert permitted_models() == []  # no allowlist, no :free suffix

    provider = OpenRouterProvider()
    assert provider.is_configured() is False
    assert "free-only" in provider.configuration_detail().lower() or "FREE" in provider.configuration_detail()

    # ... and it never even attempts a paid model.
    def fail_post(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("a paid model must never be requested")

    monkeypatch.setattr("app.services.ai.openrouter_provider.httpx.post", fail_post)
    with pytest.raises(InvalidInputError):
        provider.generate_text("hi")


def test_openrouter_allowlist_permits_explicit_paid_model(monkeypatch, openrouter_env):
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "some/paid-model")
    monkeypatch.setattr(settings, "OPENROUTER_ALLOWED_MODELS", "some/paid-model")
    assert permitted_models() == ["some/paid-model"]


def test_openrouter_free_only_false_allows_all_configured(monkeypatch, openrouter_env):
    monkeypatch.setattr(settings, "OPENROUTER_FREE_MODELS_ONLY", False)
    monkeypatch.setattr(settings, "OPENROUTER_MODEL", "paid-a")
    monkeypatch.setattr(settings, "OPENROUTER_FALLBACK_MODELS", "paid-b")
    assert permitted_models() == ["paid-a", "paid-b"]


def test_openrouter_rate_limit_and_timeout(monkeypatch, openrouter_env):
    import httpx

    provider = OpenRouterProvider()

    monkeypatch.setattr(
        "app.services.ai.openrouter_provider.httpx.post",
        lambda *a, **k: _FakeHTTPResponse(429, text='{"error":{"message":"rate limit"}}'),
    )
    with pytest.raises(RateLimitError):
        provider.generate_text("hi")

    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.services.ai.openrouter_provider.httpx.post", raise_timeout)
    with pytest.raises(ProviderTimeoutError):
        provider.generate_text("hi")


def test_openrouter_connection_error(monkeypatch, openrouter_env):
    import httpx

    provider = OpenRouterProvider()

    def raise_connect(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr("app.services.ai.openrouter_provider.httpx.post", raise_connect)
    with pytest.raises(ConnectionFailedError):
        provider.generate_text("hi")


def test_openrouter_spend_limit_blocks_requests(monkeypatch, openrouter_env):
    monkeypatch.setattr(settings, "OPENROUTER_MAX_SPEND", 5.0)
    provider = OpenRouterProvider()

    monkeypatch.setattr(
        "app.services.ai.openrouter_provider.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(payload={"data": {"usage": 10.0}}),
    )

    with pytest.raises(QuotaExceededError):
        provider.generate_text("hi")

    ok, detail = provider.check_connection()
    assert ok is False
    assert "OPENROUTER_MAX_SPEND" in detail


def test_openrouter_check_connection(monkeypatch, openrouter_env):
    provider = OpenRouterProvider()

    monkeypatch.setattr(
        "app.services.ai.openrouter_provider.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(payload={"data": []}),
    )
    ok, detail = provider.check_connection()
    assert ok is True
    assert "reachable" in detail.lower()

    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    ok, detail = provider.check_connection()
    assert ok is False
    assert "OPENROUTER_API_KEY" in detail


# ======================================================================
# Ollama provider
# ======================================================================
@pytest.fixture()
def ollama_env(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_ENABLED", True)
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "qwen2.5:1.5b")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")


def test_ollama_successful_local_generation(monkeypatch, ollama_env):
    provider = OllamaProvider()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _FakeHTTPResponse(
            payload={
                "message": {"content": "local answer"},
                "prompt_eval_count": 5,
                "eval_count": 4,
            }
        )

    monkeypatch.setattr("app.services.ai.ollama_provider.httpx.post", fake_post)

    result = provider.generate_text("hi")

    assert result.provider == "ollama"
    assert provider.inference == "local"
    assert result.model == "qwen2.5:1.5b"
    assert result.data == "local answer"
    assert result.usage == {"input_tokens": 5, "output_tokens": 4}
    assert captured["url"].endswith("/api/chat")
    assert captured["json"]["stream"] is False


def test_ollama_json_mode_sets_format(monkeypatch, ollama_env):
    provider = OllamaProvider()
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _FakeHTTPResponse(payload={"message": {"content": "{}"}})

    monkeypatch.setattr("app.services.ai.ollama_provider.httpx.post", fake_post)
    provider.generate_structured("analyze")
    assert captured["json"]["format"] == "json"


def test_ollama_missing_model_reports_pull_command(monkeypatch, ollama_env):
    provider = OllamaProvider()

    monkeypatch.setattr(
        "app.services.ai.ollama_provider.httpx.post",
        lambda *a, **k: _FakeHTTPResponse(404, text='{"error":"model not found"}'),
    )

    with pytest.raises(ModelNotFoundError) as error:
        provider.generate_text("hi")
    assert "ollama pull qwen2.5:1.5b" in str(error.value)


def test_ollama_unavailable_and_timeout(monkeypatch, ollama_env):
    import httpx

    provider = OllamaProvider()

    def raise_connect(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.services.ai.ollama_provider.httpx.post", raise_connect)
    with pytest.raises(ConnectionFailedError) as error:
        provider.generate_text("hi")
    assert "localhost:11434" in str(error.value)

    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr("app.services.ai.ollama_provider.httpx.post", raise_timeout)
    with pytest.raises(ProviderTimeoutError):
        provider.generate_text("hi")


def test_ollama_invalid_response(monkeypatch, ollama_env):
    provider = OllamaProvider()
    monkeypatch.setattr(
        "app.services.ai.ollama_provider.httpx.post",
        lambda *a, **k: _FakeHTTPResponse(payload={"unexpected": True}),
    )
    with pytest.raises(InvalidResponseError):
        provider.generate_text("hi")


def test_ollama_check_connection_states(monkeypatch, ollama_env):
    provider = OllamaProvider()

    monkeypatch.setattr(
        "app.services.ai.ollama_provider.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(payload={"models": [{"name": "qwen2.5:1.5b"}]}),
    )
    ok, detail = provider.check_connection()
    assert ok is True and "installed" in detail

    monkeypatch.setattr(
        "app.services.ai.ollama_provider.httpx.get",
        lambda *a, **k: _FakeHTTPResponse(payload={"models": [{"name": "other:7b"}]}),
    )
    ok, detail = provider.check_connection()
    assert ok is False and "ollama pull" in detail

    import httpx

    def raise_connect(*args, **kwargs):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr("app.services.ai.ollama_provider.httpx.get", raise_connect)
    ok, detail = provider.check_connection()
    assert ok is False and "not running" in detail

    monkeypatch.setattr(settings, "OLLAMA_ENABLED", False)
    ok, detail = provider.check_connection()
    assert ok is False and "disabled" in detail
