"""Centralized provider manager - selection, retry, fallback, logging.

WHAT THIS FILE DOES
    This is the ONE place where provider fallback logic lives:

      1. builds the provider chain from AI_PROVIDER_PRIORITY
         (MOCK_AI=true -> mock only; mock is never a silent fallback)
      2. executes an operation against the first CONFIGURED provider
      3. retries transient failures with exponential backoff
         (AI_MAX_RETRIES, per-provider)
      4. falls back to the next provider ONLY for fallback-eligible
         errors (429 / quota / 5xx / connection / timeout / auth /
         invalid response) - never for invalid input
      5. records one honest event per request in the execution log
      6. converts failures into clean AppError responses

WHY IT EXISTS
    No endpoint contains provider logic. Document analysis, chat and
    RAG all call manager.execute() with the same logical operation, so
    the provider can change mid-request without any route noticing.

HOW IT CONNECTS
    ai_service.analyze_text() -> execute("analyze_document", ...)
    chat_service             -> execute("answer_question", ...)
    rag_service              -> execute("answer_question", ...)
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable

from app.core.config import settings
from app.services.ai.ai_exceptions import AIProviderError, UnexpectedProviderError
from app.services.ai.execution_log import ExecutionLog, execution_log
from app.services.ai.mock_provider import MockProvider
from app.services.ai.provider_interface import AIProvider, ProviderResult
from app.utils.errors import AppError

logger = logging.getLogger("docuflow.ai")

#: friendly notice wording per error category
_FALLBACK_PHRASES = {
    "rate_limit": "rate limit was reached",
    "quota": "quota was exhausted",
    "server_error": "had a server error",
    "connection": "was unreachable",
    "timeout": "timed out",
    "auth": "rejected the configured credentials",
    "model_not_found": "has no available model",
    "unavailable": "is unavailable",
    "invalid_response": "returned an invalid response",
    "unexpected": "failed unexpectedly",
}

#: single-provider error -> (HTTP status, safe user message)
_ERROR_RESPONSES: dict[str, tuple[int, str]] = {
    "rate_limit": (503, "The AI provider rate limit was reached. Please wait a moment and try again."),
    "quota": (503, "The AI provider quota was exhausted. Please try again later."),
    "server_error": (503, "The AI provider is currently unavailable. Please try again later."),
    "connection": (503, "The AI provider is currently unavailable. Please try again later."),
    "unavailable": (503, "The AI provider is currently unavailable. Please try again later."),
    "auth": (503, "The AI provider rejected the configured API key."),
    "model_not_found": (503, "The configured AI model was not found. Check the model settings."),
    "invalid_response": (502, "The AI returned an invalid response structure. Please try again."),
    "invalid_input": (400, "The AI provider rejected the request as invalid."),
    "unexpected": (503, "The AI provider failed unexpectedly. Please try again."),
    "timeout": (504, "The AI request timed out. Please try again with a shorter document."),
}


@dataclass
class ExecutionOutcome:
    """What execute() hands back on success."""

    result: ProviderResult
    requested_provider: str
    fallback_used: bool
    notice: str | None  # non-null only when a fallback actually happened


def parse_priority(raw: str) -> list[str]:
    """Split AI_PROVIDER_PRIORITY into validated lower-case names."""
    names = [part.strip().lower() for part in raw.split(",") if part.strip()]
    known = {"gemini", "openrouter", "ollama", "mock"}
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(
            f"AI_PROVIDER_PRIORITY contains unknown providers: {', '.join(unknown)}. "
            f"Valid values: {', '.join(sorted(known))}."
        )
    if not names:
        raise ValueError("AI_PROVIDER_PRIORITY must list at least one provider.")
    return names


def build_provider_chain(cfg: Any | None = None) -> list[AIProvider]:
    """Create the ordered provider chain from configuration.

    - MOCK_AI=true  -> [MockProvider]  (explicit dev mode, offline)
    - MOCK_AI=false -> AI_PROVIDER_PRIORITY order, mock EXCLUDED
      (Mock AI must never be a silent production fallback)
    - AI_FALLBACK_ENABLED=false -> only the first provider
    """
    cfg = cfg or settings
    if cfg.MOCK_AI:
        return [MockProvider()]

    chain: list[AIProvider] = []
    for name in parse_priority(cfg.AI_PROVIDER_PRIORITY):
        if name == "mock":
            continue  # never silently added in real mode
        if name == "gemini":
            from app.services.ai.gemini_provider import GeminiProvider

            chain.append(GeminiProvider())
        elif name == "openrouter":
            from app.services.ai.openrouter_provider import OpenRouterProvider

            chain.append(OpenRouterProvider())
        elif name == "ollama":
            from app.services.ai.ollama_provider import OllamaProvider

            chain.append(OllamaProvider())

    if not cfg.AI_FALLBACK_ENABLED:
        chain = chain[:1]
    return chain


class ProviderManager:
    """Executes one logical operation across an ordered provider chain."""

    #: how long a connectivity check stays cached (seconds)
    CHECK_CACHE_SECONDS = 30.0

    def __init__(
        self,
        providers: list[AIProvider],
        *,
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
        fallback_enabled: bool = True,
        log: ExecutionLog | None = None,
        backoff_base: float = 0.5,
    ) -> None:
        self.providers = providers
        self.max_retries = max(0, int(max_retries))
        self.timeout_seconds = timeout_seconds
        self.fallback_enabled = fallback_enabled
        self.log = log if log is not None else execution_log
        self.backoff_base = backoff_base
        self._check_cache: dict[str, tuple[float, bool, str]] = {}
        self._labels = {provider.name: provider.label for provider in providers}

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(
        self,
        operation: str,
        call: Callable[[AIProvider], ProviderResult],
    ) -> ExecutionOutcome:
        """Run `call(provider)` with retries and automatic fallback.

        Raises AppError (clean HTTP error) when every eligible provider
        fails or when the error must not fall back (invalid input).
        """
        if not self.providers:
            raise AppError(_NO_PROVIDER_MESSAGE, status_code=503)

        ready = [provider for provider in self.providers if provider.is_configured()]
        if not ready:
            raise AppError(_NO_PROVIDER_MESSAGE, status_code=503)

        requested = ready[0].name
        attempts_allowed = self.max_retries + 1
        failures: list[tuple[str, AIProviderError]] = []
        started_all = time.perf_counter()

        for position, provider in enumerate(ready):
            last_error: AIProviderError | None = None

            for attempt in range(attempts_allowed):
                started = time.perf_counter()
                try:
                    result = self._call_with_timeout(lambda: call(provider))
                except AIProviderError as exc:
                    duration_ms = (time.perf_counter() - started) * 1000
                    last_error = exc
                    will_retry = exc.retryable and attempt < attempts_allowed - 1
                    logger.warning(
                        "AI %s | %s attempt %d/%d failed (%s)%s",
                        operation,
                        provider.name,
                        attempt + 1,
                        attempts_allowed,
                        exc.category,
                        " -> retrying" if will_retry else "",
                    )
                    if will_retry:
                        delay = self.backoff_base * (2**attempt)
                        if delay > 0:
                            time.sleep(delay)
                        continue
                    break
                except Exception as exc:  # noqa: BLE001 - providers should classify
                    duration_ms = (time.perf_counter() - started) * 1000
                    last_error = UnexpectedProviderError(
                        f"Unexpected error from {provider.label}."
                    )
                    logger.warning(
                        "AI %s | %s raised an unclassified error",
                        operation,
                        provider.name,
                        exc_info=True,
                    )
                    break
                else:
                    duration_ms = (time.perf_counter() - started) * 1000
                    fallback_used = provider.name != requested
                    notice: str | None = None
                    if fallback_used and failures:
                        category = failures[-1][1].category
                        notice = (
                            f"{self._label(requested)} {_FALLBACK_PHRASES.get(category, category)}. "
                            f"{provider.label} was used for this request."
                        )
                    self.log.record(
                        operation=operation,
                        requested_provider=requested,
                        provider=provider.name,
                        model=result.model,
                        duration_ms=duration_ms,
                        success=True,
                        fallback_used=fallback_used,
                        # record WHICH failure caused the fallback
                        error_category=(
                            failures[-1][1].category
                            if fallback_used and failures
                            else None
                        ),
                        usage=result.usage or None,
                    )
                    logger.info(
                        "AI %s | %s (%s) succeeded in %.0fms%s",
                        operation,
                        provider.name,
                        result.model,
                        duration_ms,
                        " via fallback" if fallback_used else "",
                    )
                    return ExecutionOutcome(
                        result=result,
                        requested_provider=requested,
                        fallback_used=fallback_used,
                        notice=notice,
                    )

            # This provider is exhausted (retry limit or non-retryable).
            if last_error is None:  # pragma: no cover - defensive
                last_error = UnexpectedProviderError(f"{provider.label} produced no result.")
            failures.append((provider.name, last_error))

            can_fallback = last_error.fallback_eligible and self.fallback_enabled
            if can_fallback and any(
                candidate.is_configured() for candidate in ready[position + 1 :]
            ):
                continue  # hand the SAME operation to the next provider

            # Fallback not allowed (invalid input) or chain exhausted.
            self._record_failure(
                operation, requested, provider, last_error, started_all
            )
            raise self._to_app_error(failures)

        # Every configured provider failed.
        self._record_failure(
            operation,
            requested,
            ready[-1],
            failures[-1][1] if failures else UnexpectedProviderError("no provider"),
            started_all,
        )
        raise self._to_app_error(failures)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _call_with_timeout(self, fn: Callable[[], ProviderResult]) -> ProviderResult:
        """Run one provider attempt with a hard wall-clock limit."""
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-mgr") as pool:
            future = pool.submit(fn)
            try:
                return future.result(timeout=self.timeout_seconds)
            except FutureTimeoutError as exc:
                future.cancel()
                raise _timeout_error(self.timeout_seconds) from exc

    def _label(self, provider_name: str) -> str:
        return self._labels.get(provider_name, provider_name.title())

    def _record_failure(
        self,
        operation: str,
        requested: str,
        provider: AIProvider,
        error: AIProviderError,
        started_all: float,
    ) -> None:
        self.log.record(
            operation=operation,
            requested_provider=requested,
            provider=provider.name,
            model=provider.current_model(),
            duration_ms=(time.perf_counter() - started_all) * 1000,
            success=False,
            fallback_used=False,
            error_category=error.category,
        )

    def _to_app_error(self, failures: list[tuple[str, AIProviderError]]) -> AppError:
        """Turn accumulated provider failures into one clean API error."""
        if len(failures) == 1:
            category = failures[0][1].category
            status, message = _ERROR_RESPONSES.get(
                category, _ERROR_RESPONSES["unavailable"]
            )
            if category == "timeout":
                message = (
                    f"The AI request exceeded the {self.timeout_seconds}s timeout. "
                    "Please try again with a shorter document."
                )
            return AppError(message, status_code=status)

        summary = ", ".join(f"{name}: {error.category}" for name, error in failures)
        last_category = failures[-1][1].category
        status = _ERROR_RESPONSES.get(last_category, _ERROR_RESPONSES["unavailable"])[0]
        return AppError(
            f"AI request failed on every configured provider ({summary}). "
            "Please try again later.",
            status_code=status,
        )

    # ------------------------------------------------------------------
    # Health snapshot (no secrets, real checks only)
    # ------------------------------------------------------------------
    def _cached_check(self, provider: AIProvider) -> tuple[bool, str]:
        now = time.monotonic()
        cached = self._check_cache.get(provider.name)
        if cached and now - cached[0] < self.CHECK_CACHE_SECONDS:
            return cached[1], cached[2]
        try:
            ok, detail = provider.check_connection()
        except Exception:  # noqa: BLE001 - a failed check is just "not reachable"
            ok, detail = False, f"{provider.label} connectivity check failed."
        self._check_cache[provider.name] = (now, ok, detail)
        return ok, detail

    def all_providers(self) -> list[AIProvider]:
        """Chain providers plus every other known provider (for health)."""
        known: dict[str, AIProvider] = {}
        from app.services.ai.gemini_provider import GeminiProvider
        from app.services.ai.ollama_provider import OllamaProvider
        from app.services.ai.openrouter_provider import OpenRouterProvider

        for provider in (GeminiProvider(), OpenRouterProvider(), OllamaProvider(), MockProvider()):
            known[provider.name] = provider
        for provider in self.providers:
            known[provider.name] = provider  # chain instances win (shared state)
        order = ["gemini", "openrouter", "ollama", "mock"]
        return [known[name] for name in order if name in known]

    def snapshot(self, *, perform_checks: bool = False) -> dict[str, Any]:
        """Safe provider status for GET /api/health/ai.

        With perform_checks=True a lightweight connectivity check runs
        (cached 30s). Without it, only configuration state is reported -
        an API key existing is never claimed as "healthy".
        """
        providers_info: dict[str, Any] = {}
        for provider in self.all_providers():
            configured = provider.is_configured()
            if not configured:
                available: bool | None = False
                detail = provider.configuration_detail()
            elif perform_checks:
                available, detail = self._cached_check(provider)
            else:
                available = None
                detail = "Configuration loaded - connectivity not checked."
            providers_info[provider.name] = {
                "label": provider.label,
                "inference": provider.inference,
                "configured": configured,
                "available": available,
                "detail": detail,
                "model": provider.current_model(),
            }

        ready = [provider for provider in self.providers if provider.is_configured()]
        active = ready[0].name if ready else None

        return {
            "active_provider": active,
            "priority": [provider.name for provider in self.providers],
            "fallback_enabled": self.fallback_enabled,
            "providers": providers_info,
        }


_NO_PROVIDER_MESSAGE = (
    "No AI provider is configured. Set MOCK_AI=true for local Mock mode, "
    "or configure a provider API key (GEMINI_API_KEY / OPENROUTER_API_KEY) "
    "or enable Ollama (OLLAMA_ENABLED=true)."
)


def _timeout_error(seconds: float) -> AIProviderError:
    from app.services.ai.ai_exceptions import ProviderTimeoutError

    return ProviderTimeoutError(
        f"The AI request exceeded the {seconds}s timeout."
    )


# ----------------------------------------------------------------------
# Process-wide manager (built once from settings)
# ----------------------------------------------------------------------
from functools import lru_cache  # noqa: E402 - placed here for readability


@lru_cache(maxsize=1)
def _build_manager() -> ProviderManager:
    return ProviderManager(
        build_provider_chain(settings),
        max_retries=settings.AI_MAX_RETRIES,
        timeout_seconds=settings.AI_REQUEST_TIMEOUT,
        fallback_enabled=settings.AI_FALLBACK_ENABLED,
        log=execution_log,
    )


def get_provider_manager() -> ProviderManager:
    """Lazily build (and cache) the singleton manager from settings."""
    return _build_manager()


def reset_provider_manager() -> None:
    """Drop the cached manager so tests can rebuild it after env changes."""
    _build_manager.cache_clear()
