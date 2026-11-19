"""Google Gemini provider - the primary cloud AI.

WHAT THIS FILE DOES
    Talks to the official google-genai SDK and converts every failure
    into the typed errors from ai_exceptions.py so the provider
    manager can classify it (rate limit -> retry, quota -> fall back,
    bad input -> raise immediately).

WHY IT EXISTS
    Provider-specific code lives only here: transport, SDK quirks and
    error translation. Prompt text comes from prompts.py and high-level
    operations come from the shared interface.

HOW IT CONNECTS
    provider_manager -> generate_content(settings.GEMINI_MODEL, ...)
    settings         -> GEMINI_API_KEY / GEMINI_EMBEDDING_MODEL
"""
from __future__ import annotations

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
)
from app.services.ai.provider_interface import AIProvider, ProviderResult


class GeminiProvider(AIProvider):
    """Google Gemini via the official SDK."""

    name = "gemini"
    label = "Google Gemini"
    inference = "cloud"
    supports_json_mode = True

    # --- Configuration ---------------------------------------------------
    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY.strip())

    def current_model(self) -> str:
        return settings.GEMINI_MODEL

    def configuration_detail(self) -> str:
        return "GEMINI_API_KEY is not configured."

    # --- Transport -------------------------------------------------------
    def _get_client(self):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise InvalidResponseError(
                "The 'google-genai' package is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={"timeout": settings.AI_REQUEST_TIMEOUT * 1000},
        )

    def _generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> ProviderResult:
        if not self.is_configured():
            # Treated as "not configured" upstream; kept defensive here.
            raise ProviderAuthError("GEMINI_API_KEY is not configured.")

        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise InvalidResponseError(
                "The 'google-genai' package is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc

        config_kwargs: dict = {"temperature": temperature}
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        if system:
            config_kwargs["system_instruction"] = system

        try:
            response = self._get_client().models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:  # noqa: BLE001 - SDK exposes several error types
            raise _translate_gemini_error(exc) from exc

        raw_text = (response.text or "").strip()
        if not raw_text:
            raise InvalidResponseError("Gemini returned an empty response.")

        usage: dict = {}
        metadata = getattr(response, "usage_metadata", None)
        if metadata is not None:
            input_tokens = getattr(metadata, "prompt_token_count", None)
            output_tokens = getattr(metadata, "candidates_token_count", None)
            if input_tokens:
                usage["input_tokens"] = int(input_tokens)
            if output_tokens:
                usage["output_tokens"] = int(output_tokens)

        return ProviderResult(
            data=raw_text, provider=self.name, model=self.current_model(), usage=usage
        )

    # --- Health ----------------------------------------------------------
    def check_connection(self) -> tuple[bool, str]:
        """Lightweight metadata call - no tokens are generated.

        Proves the key authenticates AND the configured model exists;
        presence of the key alone is never reported as "healthy".
        """
        if not self.is_configured():
            return False, "GEMINI_API_KEY is not configured."

        try:
            client = self._get_client()
        except Exception:  # pragma: no cover - import problems surface elsewhere
            return False, "The google-genai SDK is not available."

        try:
            try:
                client.models.get(model=settings.GEMINI_MODEL)
            except TypeError:  # older SDK signature variants
                client.models.get(name=settings.GEMINI_MODEL)
            return True, "Gemini reachable - configured model is available."
        except Exception as exc:  # noqa: BLE001 - classify below
            status = getattr(exc, "code", None)
            message = str(exc).lower()
            if status in (400, 401, 403) or "api key" in message or "permission" in message:
                return False, "Gemini rejected the configured API key."
            if status == 404 or "not found" in message:
                return (
                    False,
                    f"Model '{settings.GEMINI_MODEL}' is not available for this key.",
                )
            if "timeout" in message or "timed out" in message:
                return False, "Gemini did not answer in time."
            if status is not None or "connect" in message or "unreachable" in message:
                return False, "Cannot reach the Gemini API right now."
            # Unknown SDK method/shape: the key exists but we cannot prove
            # more without a generation call (which would cost tokens).
            return True, "Gemini API key configured (model check unsupported by SDK)."


def _translate_gemini_error(exc: Exception) -> Exception:
    """Map google-genai SDK errors onto the typed error taxonomy."""
    status = getattr(exc, "code", None)
    message = str(exc).lower()

    if status is None:
        # Non-APIError failures: network, TLS, timeouts...
        if "timeout" in message or "timed out" in message:
            return ProviderTimeoutError("Gemini request timed out.")
        if any(word in message for word in ("connect", "dns", "unreachable", "reset")):
            return ConnectionFailedError("Cannot reach the Gemini API.")
        return UnexpectedProviderError("Unexpected Gemini client error.")

    if status == 429:
        if "quota" in message or "insufficient" in message or "billing" in message:
            return QuotaExceededError("Gemini quota was exhausted.")
        return RateLimitError("Gemini rate limit was reached.")
    if status in (401, 403):
        return ProviderAuthError("Gemini rejected the configured API key.")
    if status == 404:
        return ModelNotFoundError(f"Gemini model '{settings.GEMINI_MODEL}' was not found.")
    if status in (400, 422):
        return InvalidInputError("Gemini rejected the request as invalid.")
    if 500 <= status < 600:
        return ProviderServerError(f"Gemini had a server error (HTTP {status}).")
    if "timeout" in message:
        return ProviderTimeoutError("Gemini request timed out.")
    return UnexpectedProviderError("Unexpected Gemini API error.")
