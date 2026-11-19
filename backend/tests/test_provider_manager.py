"""Provider manager tests: selection, retries, fallback, logging.

All providers here are in-memory fakes - the suite never performs a
real API call.
"""
import time

import pytest

from app.core.config import settings
from app.services.ai.ai_exceptions import (
    InvalidInputError,
    ProviderTimeoutError,
    QuotaExceededError,
    RateLimitError,
)
from app.services.ai.execution_log import ExecutionLog
from app.services.ai.mock_provider import MockProvider
from app.services.ai.provider_interface import AIProvider, ProviderResult
from app.services.ai.provider_manager import (
    ProviderManager,
    build_provider_chain,
    parse_priority,
)
from app.utils.errors import AppError


class FakeProvider(AIProvider):
    """Scripted provider: each call consumes the next scripted item.

    Script items: Exception -> raised, ProviderResult -> returned.
    When the script is exhausted the LAST item repeats forever.
    """

    def __init__(self, name, label=None, script=None, configured=True, model="fake-1"):
        self.name = name
        self.label = label or name.title()
        self.script = list(script or [])
        self._configured = configured
        self.model = model
        self.calls = 0

    def is_configured(self):
        return self._configured

    def current_model(self):
        return self.model

    def check_connection(self):
        return self._configured, f"{self.label} fake connectivity check"

    def _generate(self, prompt, *, system=None, temperature=0.2, json_mode=False):
        self.calls += 1
        if not self.script:
            return ProviderResult(data=f"ok from {self.name}", provider=self.name, model=self.model)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item()
        return item


def make_manager(providers, **overrides):
    defaults = dict(
        max_retries=0,
        timeout_seconds=5.0,
        fallback_enabled=True,
        log=ExecutionLog(),
        backoff_base=0.0,
    )
    defaults.update(overrides)
    return ProviderManager(providers, **defaults)


def ok(name, model="fake-1"):
    return ProviderResult(data=f"ok from {name}", provider=name, model=model)


# --- Chain construction ------------------------------------------------
def test_mock_mode_builds_mock_only_chain(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_AI", True)
    chain = build_provider_chain(settings)
    assert [provider.name for provider in chain] == ["mock"]
    assert isinstance(chain[0], MockProvider)


def test_real_mode_builds_priority_chain_without_mock(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_AI", False)
    monkeypatch.setattr(settings, "AI_PROVIDER_PRIORITY", "gemini,openrouter,ollama,mock")
    chain = build_provider_chain(settings)
    assert [provider.name for provider in chain] == ["gemini", "openrouter", "ollama"]
    assert "mock" not in [provider.name for provider in chain]  # never silent


def test_fallback_disabled_keeps_only_first_provider(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_AI", False)
    monkeypatch.setattr(settings, "AI_PROVIDER_PRIORITY", "gemini,openrouter")
    monkeypatch.setattr(settings, "AI_FALLBACK_ENABLED", False)
    chain = build_provider_chain(settings)
    assert [provider.name for provider in chain] == ["gemini"]


def test_parse_priority_rejects_unknown_and_empty():
    assert parse_priority("gemini, openrouter") == ["gemini", "openrouter"]
    with pytest.raises(ValueError):
        parse_priority("gemini,chatgpt")
    with pytest.raises(ValueError):
        parse_priority("  ,  ")


# --- Success without fallback ------------------------------------------
def test_first_provider_success_does_not_touch_others():
    primary = FakeProvider("gemini", script=[ok("gemini")])
    secondary = FakeProvider("openrouter")
    manager = make_manager([primary, secondary])

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert outcome.result.provider == "gemini"
    assert outcome.fallback_used is False
    assert outcome.notice is None
    assert secondary.calls == 0
    assert manager.log.metrics()["requests"] == 1
    assert manager.log.metrics()["success"] == 1


# --- Fallback transitions ----------------------------------------------
def test_rate_limited_primary_falls_back_with_notice():
    primary = FakeProvider(
        "gemini", label="Google Gemini",
        script=[RateLimitError("429")],
    )
    secondary = FakeProvider(
        "openrouter", label="OpenRouter", script=[ok("openrouter", "free-model:free")]
    )
    manager = make_manager([primary, secondary])

    outcome = manager.execute("answer_question", lambda p: p.generate_text("hi"))

    assert outcome.result.provider == "openrouter"
    assert outcome.fallback_used is True
    assert outcome.requested_provider == "gemini"
    assert "Google Gemini rate limit was reached" in outcome.notice
    assert "OpenRouter was used for this request" in outcome.notice

    metrics = manager.log.metrics()
    assert metrics["fallback_events"] == 1
    fallbacks = manager.log.recent_fallbacks()
    assert fallbacks[-1]["from"] == "gemini"
    assert fallbacks[-1]["to"] == "openrouter"
    assert fallbacks[-1]["error_category"] == "rate_limit"


def test_three_provider_chain_falls_back_twice():
    first = FakeProvider("gemini", script=[QuotaExceededError("quota")])
    second = FakeProvider("openrouter", script=[RateLimitError("429")])
    third = FakeProvider("ollama", script=[ok("ollama", "qwen2.5:1.5b")])
    manager = make_manager([first, second, third])

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert outcome.result.provider == "ollama"
    assert outcome.fallback_used is True
    assert first.calls == 1 and second.calls == 1 and third.calls == 1


def test_all_providers_fail_returns_clean_summary_error():
    first = FakeProvider("gemini", script=[RateLimitError("429")])
    second = FakeProvider("openrouter", script=[QuotaExceededError("quota")])
    manager = make_manager([first, second])

    with pytest.raises(AppError) as error:
        manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert error.value.status_code == 503
    assert "gemini: rate_limit" in error.value.detail
    assert "openrouter: quota" in error.value.detail
    assert manager.log.metrics()["failed"] == 1
    assert manager.log.metrics()["requests"] == 1


def test_invalid_input_never_falls_back():
    primary = FakeProvider("gemini", script=[InvalidInputError("bad request")])
    secondary = FakeProvider("openrouter")
    manager = make_manager([primary, secondary])

    with pytest.raises(AppError) as error:
        manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert error.value.status_code == 400  # not a provider outage
    assert secondary.calls == 0  # no fallback for invalid input


def test_fallback_disabled_raises_after_first_provider():
    primary = FakeProvider("gemini", script=[RateLimitError("429")])
    secondary = FakeProvider("openrouter")
    manager = make_manager([primary, secondary], fallback_enabled=False)

    with pytest.raises(AppError):
        manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert secondary.calls == 0


def test_unconfigured_providers_are_skipped():
    missing_key = FakeProvider("gemini", configured=False)
    working = FakeProvider("openrouter", script=[ok("openrouter")])
    manager = make_manager([missing_key, working])

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    # Unconfigured providers do not count as a fallback attempt.
    assert outcome.result.provider == "openrouter"
    assert outcome.fallback_used is False
    assert missing_key.calls == 0


def test_no_configured_provider_raises_clear_503():
    manager = make_manager([FakeProvider("gemini", configured=False)])

    with pytest.raises(AppError) as error:
        manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert error.value.status_code == 503
    assert "No AI provider is configured" in error.value.detail


def test_empty_chain_raises_clear_503():
    manager = make_manager([])
    with pytest.raises(AppError) as error:
        manager.execute("analyze_document", lambda p: p.generate_text("hi"))
    assert error.value.status_code == 503


# --- Retries ------------------------------------------------------------
def test_transient_error_is_retried_on_same_provider():
    provider = FakeProvider(
        "gemini",
        script=[RateLimitError("429"), ok("gemini")],  # fail once, then succeed
    )
    manager = make_manager([provider], max_retries=1)

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert outcome.result.provider == "gemini"
    assert provider.calls == 2  # one retry happened
    assert outcome.notice is None  # no provider switch -> no notice


def test_retries_exhausted_then_fallback():
    primary = FakeProvider("gemini", script=[RateLimitError("429")])
    secondary = FakeProvider("openrouter", script=[ok("openrouter")])
    manager = make_manager([primary, secondary], max_retries=2)

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert primary.calls == 3  # initial + 2 retries
    assert outcome.result.provider == "openrouter"


# --- Timeout ------------------------------------------------------------
def test_provider_timeout_becomes_504():
    def slow():
        time.sleep(0.4)
        return ok("gemini")

    slow_provider = FakeProvider("gemini", script=[slow])
    manager = make_manager([slow_provider], timeout_seconds=0.05)

    with pytest.raises(AppError) as error:
        manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert error.value.status_code == 504


def test_timeout_is_fallback_eligible():
    def slow():
        time.sleep(0.3)
        return ok("gemini")

    slow_provider = FakeProvider("gemini", script=[slow])
    healthy = FakeProvider("openrouter", script=[ok("openrouter")])
    manager = make_manager([slow_provider, healthy], timeout_seconds=0.05)

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))
    assert outcome.result.provider == "openrouter"


# --- Mock mode (explicit only) -----------------------------------------
def test_mock_provider_is_used_only_when_explicitly_enabled():
    manager = make_manager([MockProvider()])

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert outcome.result.provider == "mock"
    assert outcome.result.model == "-"
    assert outcome.notice is None


# --- Execution logging --------------------------------------------------
def test_execution_log_records_safe_fields_only():
    log = ExecutionLog()
    provider = FakeProvider("gemini", script=[ok("gemini", "gemini-x")])
    manager = make_manager([provider], log=log)

    manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    event = log.snapshot()["metrics"]
    assert event["requests"] == 1
    assert event["success"] == 1
    assert event["avg_response_time_ms"] >= 0

    # Re-run to inspect a full event through recent_fallbacks (none here).
    assert log.recent_fallbacks() == []

    provider.script = [QuotaExceededError("quota")]
    secondary = FakeProvider("openrouter", script=[ok("openrouter")])
    manager2 = make_manager([provider, secondary], log=log)
    manager2.execute("answer_question", lambda p: p.generate_text("hi"))
    fallback = log.recent_fallbacks()[-1]
    assert set(fallback) == {"at", "operation", "from", "to", "error_category"}
    assert "key" not in str(fallback).lower()


def test_unexpected_provider_exception_is_contained():
    primary = FakeProvider("gemini", script=[ValueError("boom - never leaks")])
    secondary = FakeProvider("openrouter", script=[ok("openrouter")])
    manager = make_manager([primary, secondary])

    outcome = manager.execute("analyze_document", lambda p: p.generate_text("hi"))

    assert outcome.result.provider == "openrouter"
    assert "boom" not in (outcome.notice or "")
