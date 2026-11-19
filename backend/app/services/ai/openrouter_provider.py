"""OpenRouter provider - the cloud fallback (OpenAI-compatible API).

WHAT THIS FILE DOES
    Talks to https://openrouter.ai/api/v1/chat/completions with plain
    httpx, classifies HTTP failures into the shared error taxonomy and
    enforces the free-model-only cost guard.

COST PROTECTION (OPENROUTER_FREE_MODELS_ONLY=true)
    Only models that are explicitly permitted may be used:
      - models listed in OPENROUTER_ALLOWED_MODELS, or
      - when no allowlist is given, only ids ending in ":free".
    A configured model that is not permitted is excluded - the manager
    then skips OpenRouter entirely (or the caller gets a clear error).
    Paid models are NEVER selected silently.

HOW IT CONNECTS
    provider_manager -> POST /chat/completions with OPENROUTER_MODEL
        (+ OPENROUTER_FALLBACK_MODELS tried in order on model errors)
"""
from __future__ import annotations

import time

import httpx

from app.core.config import settings
from app.services.ai.ai_exceptions import (
    AIProviderError,
    ConnectionFailedError,
    InvalidInputError,
    InvalidResponseError,
    ModelNotFoundError,
    ProviderAuthError,
    ProviderServerError,
    ProviderTimeoutError,
    QuotaExceededError,
    RateLimitError,
    classify_status_code,
)
from app.services.ai.provider_interface import AIProvider, ProviderResult

BASE_URL = "https://openrouter.ai/api/v1"
_SPEND_CACHE_SECONDS = 60.0
_BODY_SNIPPET_LIMIT = 300  # never log/store huge provider bodies


def permitted_models() -> list[str]:
    """Configured OpenRouter models that pass the free-only guard.

    Order is preserved: OPENROUTER_MODEL first, then the fallback list.
    Empty result => OpenRouter is unusable in this configuration, which
    is reported honestly instead of silently picking a paid model.
    """
    candidates: list[str] = []
    for raw in [settings.OPENROUTER_MODEL, *settings.OPENROUTER_FALLBACK_MODELS.split(",")]:
        cleaned = raw.strip()
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    if not settings.OPENROUTER_FREE_MODELS_ONLY:
        return candidates

    allowed = {
        model.strip()
        for model in settings.OPENROUTER_ALLOWED_MODELS.split(",")
        if model.strip()
    }
    if allowed:
        # Explicit allowlist wins: only names the operator approved.
        return [model for model in candidates if model in allowed]
    # No allowlist configured -> only provably free (":free") ids pass.
    return [model for model in candidates if model.endswith(":free")]


class OpenRouterProvider(AIProvider):
    """OpenRouter via its OpenAI-compatible HTTP API."""

    name = "openrouter"
    label = "OpenRouter"
    inference = "cloud"
    supports_json_mode = True

    def __init__(self) -> None:
        self._spend_cache: tuple[float, bool, str] | None = None

    # --- Configuration ---------------------------------------------------
    def is_configured(self) -> bool:
        return bool(settings.OPENROUTER_API_KEY.strip()) and bool(permitted_models())

    def current_model(self) -> str:
        models = permitted_models()
        return models[0] if models else "-"

    def configuration_detail(self) -> str:
        if not settings.OPENROUTER_API_KEY.strip():
            return "OPENROUTER_API_KEY is not configured."
        if not permitted_models():
            return (
                "No permitted model: OPENROUTER_FREE_MODELS_ONLY excludes every "
                "configured OpenRouter model."
            )
        return "OpenRouter is not configured."

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY.strip()}",
            "Content-Type": "application/json",
            "X-Title": "DocuFlow AI",
        }

    # --- Spend limit (only when OPENROUTER_MAX_SPEND > 0) ----------------
    def _spend_verdict(self) -> tuple[bool, str]:
        """Cached usage check against the configured spend limit.

        Zero extra API calls when OPENROUTER_MAX_SPEND is unset (0).
        A failed check never blocks requests - it just re-checks later.
        """
        limit = settings.OPENROUTER_MAX_SPEND
        if limit <= 0:
            return True, ""

        now = time.monotonic()
        if self._spend_cache and now - self._spend_cache[0] < _SPEND_CACHE_SECONDS:
            _, ok, detail = self._spend_cache
            return ok, detail

        ok, detail = True, ""
        try:
            response = httpx.get(
                f"{BASE_URL}/auth/key",
                headers=self._headers(),
                timeout=10.0,
            )
            if response.status_code < 400:
                usage = float(response.json().get("data", {}).get("usage") or 0.0)
                if usage >= limit:
                    ok = False
                    detail = (
                        f"OPENROUTER_MAX_SPEND reached (${usage:.2f} of ${limit:.2f})."
                    )
        except (httpx.HTTPError, ValueError, KeyError):
            ok, detail = True, ""  # cannot verify -> do not block the feature

        self._spend_cache = (now, ok, detail)
        return ok, detail

    # --- Transport -------------------------------------------------------
    def _call_model(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None,
        temperature: float,
        json_mode: bool,
    ) -> ProviderResult:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode and self.supports_json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = httpx.post(
                f"{BASE_URL}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=settings.AI_REQUEST_TIMEOUT,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("OpenRouter request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ConnectionFailedError("Cannot reach OpenRouter.") from exc

        if response.status_code >= 400:
            body = response.text[:_BODY_SNIPPET_LIMIT]
            # A 400 while asking for JSON often means the model does not
            # support response_format - the caller retries without it.
            raise classify_status_code(response.status_code, body)

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise InvalidResponseError("OpenRouter returned a malformed response.") from exc

        if not isinstance(content, str) or not content.strip():
            raise InvalidResponseError("OpenRouter returned an empty completion.")

        usage: dict = {}
        raw_usage = data.get("usage") or {}
        if isinstance(raw_usage, dict):
            if raw_usage.get("prompt_tokens"):
                usage["input_tokens"] = int(raw_usage["prompt_tokens"])
            if raw_usage.get("completion_tokens"):
                usage["output_tokens"] = int(raw_usage["completion_tokens"])

        return ProviderResult(
            data=content, provider=self.name, model=model, usage=usage
        )

    def _generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> ProviderResult:
        if not settings.OPENROUTER_API_KEY.strip():
            raise ProviderAuthError("OPENROUTER_API_KEY is not configured.")

        spend_ok, spend_detail = self._spend_verdict()
        if not spend_ok:
            raise QuotaExceededError(spend_detail or "OpenRouter spend limit reached.")

        models = permitted_models()
        if not models:
            raise InvalidInputError(
                "No permitted OpenRouter model is configured "
                "(OPENROUTER_FREE_MODELS_ONLY excludes every candidate)."
            )

        last_error: AIProviderError | None = None
        for model in models:
            try:
                return self._call_model(
                    model, prompt, system=system, temperature=temperature,
                    json_mode=json_mode,
                )
            except InvalidInputError:
                if not json_mode:
                    raise
                # Maybe this model does not support response_format:
                # one cheap retry without it (a 400 never spends tokens).
                try:
                    return self._call_model(
                        model, prompt, system=system, temperature=temperature,
                        json_mode=False,
                    )
                except InvalidInputError:
                    raise
            except ModelNotFoundError as exc:
                # This model id is wrong/unavailable -> try the next one.
                last_error = exc
                continue

        raise last_error or ProviderAuthError("No usable OpenRouter model.")

    # --- Health ----------------------------------------------------------
    def check_connection(self) -> tuple[bool, str]:
        """Reachability + model permission + optional spend limit."""
        if not settings.OPENROUTER_API_KEY.strip():
            return False, "OPENROUTER_API_KEY is not configured."

        models = permitted_models()
        if not models:
            return (
                False,
                "No permitted model: free-only mode excludes every configured "
                "OpenRouter model.",
            )

        spend_ok, spend_detail = self._spend_verdict()
        if not spend_ok:
            return False, spend_detail

        try:
            response = httpx.get(f"{BASE_URL}/models", timeout=10.0)
        except httpx.HTTPError:
            return False, "Cannot reach OpenRouter right now."
        if response.status_code >= 500:
            return False, f"OpenRouter had a server error (HTTP {response.status_code})."
        if response.status_code >= 400:
            return False, "OpenRouter rejected the models request."

        return True, f"OpenRouter reachable - using model '{models[0]}'."
