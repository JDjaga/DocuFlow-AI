"""Typed AI provider errors and their retry / fallback classification.

WHAT THIS FILE DOES
    Every provider converts its SDK / HTTP failures into one of these
    classes. Each class carries two flags the provider manager reads:

        retryable        -> safe to retry on the SAME provider
                            (429, 5xx, connection, timeout)
        fallback_eligible -> safe to try the NEXT provider
                            (quota, auth rejected, provider down)

    Invalid input errors are neither: they would fail identically on
    every other provider, so the manager raises them immediately.

WHY IT EXISTS
    Fallback decisions must never be spread across endpoints as string
    matching ("if '429' in message..."). One classifier, one place.

HOW IT CONNECTS
    gemini_provider / openrouter_provider / ollama_provider raise these
        -> provider_manager.execute() reads .retryable / .fallback_eligible
        -> decides retry, fallback, or immediate error
"""
from __future__ import annotations


class AIProviderError(Exception):
    """Base class for provider-side failures.

    `safe_message` is short and never contains keys, headers or raw
    document content - it is safe to log and to summarise for the API.
    """

    category = "provider_error"
    retryable = False
    fallback_eligible = False

    def __init__(self, message: str = ""):
        super().__init__(message or self.category)
        self.safe_message = message or self.category


# --- Fallback-eligible, retryable on the same provider ----------------
class RateLimitError(AIProviderError):
    """HTTP 429 - too many requests. Wait and retry, then fall back."""

    category = "rate_limit"
    retryable = True
    fallback_eligible = True


class ProviderServerError(AIProviderError):
    """HTTP 5xx - the provider itself is having problems."""

    category = "server_error"
    retryable = True
    fallback_eligible = True


class ConnectionFailedError(AIProviderError):
    """Cannot reach the provider at all (DNS, refused, reset)."""

    category = "connection"
    retryable = True
    fallback_eligible = True


class ProviderTimeoutError(AIProviderError):
    """The provider did not answer within the configured timeout."""

    category = "timeout"
    retryable = True
    fallback_eligible = True


# --- Fallback-eligible, NOT worth retrying on the same provider -------
class QuotaExceededError(AIProviderError):
    """Billing / daily quota exhausted - retrying now cannot help."""

    category = "quota"
    retryable = False
    fallback_eligible = True


class ProviderAuthError(AIProviderError):
    """The provider rejected the configured API key / permission."""

    category = "auth"
    retryable = False
    fallback_eligible = True


class ModelNotFoundError(AIProviderError):
    """The configured model id does not exist on this provider."""

    category = "model_not_found"
    retryable = False
    fallback_eligible = True


class InvalidResponseError(AIProviderError):
    """Provider answered, but with malformed / schema-breaking output."""

    category = "invalid_response"
    retryable = False
    fallback_eligible = True


class ProviderUnavailableError(AIProviderError):
    """Provider explicitly reports it is unavailable (local runtime down...)."""

    category = "unavailable"
    retryable = False
    fallback_eligible = True


# --- Never falls back ---------------------------------------------------
class InvalidInputError(AIProviderError):
    """The request itself is invalid - every provider would reject it."""

    category = "invalid_input"
    retryable = False
    fallback_eligible = False


class UnexpectedProviderError(AIProviderError):
    """Unclassified provider bug. One hop forward, never a retry."""

    category = "unexpected"
    retryable = False
    fallback_eligible = True


# --- Classification helpers --------------------------------------------
def classify_status_code(status_code: int, body: str = "") -> AIProviderError:
    """Map an HTTP status code (plus optional response body) to a typed error.

    Used by the OpenRouter and Ollama providers, which speak plain HTTP.
    """
    lowered = (body or "").lower()

    if status_code == 429:
        if "quota" in lowered or "insufficient" in lowered or "credit" in lowered:
            return QuotaExceededError("The provider quota was exhausted (HTTP 429).")
        return RateLimitError("The provider rate limit was reached (HTTP 429).")

    if status_code in (401, 403):
        return ProviderAuthError("The provider rejected the configured credentials.")

    if status_code == 404:
        # On model-scoped endpoints a 404 means the model id is wrong.
        if "model" in lowered:
            return ModelNotFoundError("The configured model was not found (HTTP 404).")
        return InvalidInputError("The provider could not find the requested resource (HTTP 404).")

    if status_code in (400, 413, 422):
        return InvalidInputError(f"The provider rejected the request (HTTP {status_code}).")

    if 500 <= status_code < 600:
        return ProviderServerError(f"The provider had a server error (HTTP {status_code}).")

    return ProviderUnavailableError(f"The provider returned an unexpected status (HTTP {status_code}).")
