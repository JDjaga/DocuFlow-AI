"""AI service layer - the single entry point for document analysis.

WHAT THIS FILE DOES
    1. runs the request through the CENTRALIZED provider manager
       (Gemini -> OpenRouter -> Ollama, with retries and fallback)
    2. validates/normalises the JSON with the existing Pydantic schema
    3. converts any failure into a clean, safe API error
    4. describes the active AI setup for GET /api/health/ai

WHY IT EXISTS
    Everything else in the backend calls `analyze_text()` and gets a
    guaranteed `AIAnalysis` object back. No router or service ever talks
    to a provider directly - the fallback chain lives in exactly one
    place (services/ai/provider_manager.py).

HOW IT CONNECTS
    routers/documents.py -> document_service.analyze_and_save()
                          -> ai_service.analyze_text(text)
                          -> provider_manager.execute("analyze_document")
                          -> gemini | openrouter | ollama | mock

INTERVIEW NOTE
    "I isolate the AI behind a service boundary: input is text, output is
     a validated Pydantic model, and every failure mode (timeout, rate
     limit, malformed JSON) is translated into an HTTP status code."
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ai import AIAnalysis
from app.services.ai import execution_log, get_provider_manager, reset_provider_manager
from app.services.ai.ai_exceptions import InvalidResponseError
from app.services.ai.embedding_service import get_embedding_service, local_embeddings_available
from app.services.ai.response_validator import validate_analysis
from app.utils.errors import AppError, service_unavailable

logger = logging.getLogger("docuflow.ai")

# Kept so `from app.services.ai_service import reset_provider_manager`
# style test helpers keep working after the upgrade.
__all__ = [
    "analyze_text",
    "ensure_text_length",
    "health_check",
    "provider_info",
    "reset_ai_services",
]


def analyze_text(text: str) -> tuple[AIAnalysis, str, str | None]:
    """Analyze document text through the provider manager.

    Returns:
        (validated analysis, actual provider name, fallback notice)
        where provider is 'gemini' | 'openrouter' | 'ollama' | 'mock'
        and fallback notice is None unless a fallback really happened.

    Raises:
        AppError with 400/502/503/504 when every eligible provider fails.
    """
    manager = get_provider_manager()

    def _call(provider):
        result = provider.analyze_document(text)
        # Schema validation happens INSIDE the manager call, so a
        # malformed reply from one provider falls back to the next.
        result.data = validate_analysis(result.data)
        return result

    outcome = manager.execute("analyze_document", _call)
    return outcome.result.data, outcome.result.provider, outcome.notice


def _validate(payload) -> AIAnalysis:
    """Strict Pydantic validation of whatever the provider returned.

    Kept as a small public helper (used by tests): converts validation
    failures into the same clean 502 the API has always returned.
    """
    try:
        return validate_analysis(payload)
    except (InvalidResponseError, ValidationError, ValueError) as exc:
        raise AppError(
            "The AI returned an invalid response structure. Please try again.",
            status_code=502,
        ) from exc


def _mode_label(provider_name: str) -> str:
    labels = {
        "mock": "Mock AI (simulated analysis)",
        "gemini": "Google Gemini (real AI)",
        "openrouter": "OpenRouter (real AI)",
        "ollama": "Ollama (local AI)",
        "none": "No AI provider configured",
    }
    return labels.get(provider_name, provider_name)


def provider_info(*, perform_checks: bool = False) -> dict:
    """Safe description of the AI setup (no secrets).

    With perform_checks=True the returned provider list contains real
    connectivity results (cached 30s); otherwise only config state.
    """
    manager = get_provider_manager()
    snapshot = manager.snapshot(perform_checks=perform_checks)
    active = snapshot["active_provider"]

    model = "-"
    if active and active != "mock":
        model = snapshot["providers"][active]["model"]

    try:
        embedding = _embedding_info()
    except Exception as exc:  # noqa: BLE001 - health must never crash
        embedding = {"status": "unavailable", "detail": str(exc)[:200]}

    return {
        "provider": active or "none",
        "mode": _mode_label(active or "none"),
        "model": model,
        "api_key_configured": bool(
            settings.GEMINI_API_KEY.strip() or settings.OPENROUTER_API_KEY.strip()
        ),
        "timeout_seconds": settings.AI_REQUEST_TIMEOUT,
        "max_input_chars": settings.MAX_INPUT_CHARS,
        "priority": snapshot["priority"],
        "fallback_enabled": snapshot["fallback_enabled"],
        "providers": snapshot["providers"],
        "embedding": embedding,
    }


def _embedding_info() -> dict:
    """Embedding configuration for the health endpoint (no API calls)."""
    try:
        service = get_embedding_service()
    except Exception as exc:  # noqa: BLE001
        return {
            "provider": "-",
            "model": "-",
            "dimension": None,
            "status": "unavailable",
            "detail": str(exc)[:200],
        }

    dimension = service.expected_dimension()
    detail = f"{service.provider_name} / {service.model_name}"
    if service.provider_name == "mock":
        detail = "Deterministic local mock embeddings (simulated, offline)."
    elif service.provider_name == "gemini":
        detail += " - connectivity not tested until first use."
    elif service.provider_name == "local":
        if not local_embeddings_available():
            # Package present but not importable -> say so, never pretend.
            return {
                "provider": "local",
                "model": service.model_name,
                "dimension": None,
                "status": "unavailable",
                "detail": (
                    "sentence-transformers cannot be imported (broken "
                    "dependencies). Run: pip install -U sentence-transformers"
                ),
            }
        detail += " - runs offline through sentence-transformers."

    return {
        "provider": service.provider_name,
        "model": service.model_name,
        "dimension": dimension,
        "status": "configured",
        "detail": detail,
    }


def health_check() -> dict:
    """Component health used by GET /api/health/ai.

    Performs REAL lightweight connectivity checks (cached 30s) for
    configured providers - a key merely existing is never reported as
    healthy. Metrics come from the execution log (real events only).
    """
    manager = get_provider_manager()
    snapshot = manager.snapshot(perform_checks=True)
    providers = snapshot["providers"]
    active = snapshot["active_provider"]

    if settings.MOCK_AI:
        status = "healthy"
        detail = "Mock AI mode is active - no external API required."
    elif active is None:
        status = "unavailable"
        detail = (
            "No AI provider is configured. Set MOCK_AI=true for local mode "
            "or add a provider API key."
        )
    else:
        active_info = providers[active]
        fallbacks_available = any(
            info["configured"] and info["available"]
            for name, info in providers.items()
            if name != active
        )
        if active_info["available"]:
            status = "healthy"
            detail = f"{active_info['label']} is reachable. {active_info['detail']}"
        elif fallbacks_available:
            status = "degraded"
            detail = (
                f"{active_info['label']} is unavailable "
                f"({active_info['detail']}) - automatic fallback will use "
                "the next configured provider."
            )
        else:
            status = "unavailable"
            detail = f"No AI provider is reachable. {active_info['detail']}"

    info = provider_info(perform_checks=True)  # keep the checked provider list
    log_snapshot = execution_log.snapshot()

    return {
        "status": status,
        "detail": detail,
        **info,
        "metrics": log_snapshot["metrics"],
        "recent_fallbacks": log_snapshot["recent_fallbacks"],
    }


def ensure_text_length(text: str) -> str:
    """Guard against absurdly large inputs before they reach a provider."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise service_unavailable("The document contains no text to analyze.")
    if len(cleaned) > settings.MAX_INPUT_CHARS:
        raise AppError(
            f"Document is too long ({len(cleaned)} characters). "
            f"Maximum supported is {settings.MAX_INPUT_CHARS} characters.",
            status_code=413,
        )
    return cleaned


def reset_ai_services() -> None:
    """Rebuild cached AI singletons after settings changes (tests)."""
    reset_provider_manager()
    from app.services.ai.embedding_service import reset_embedding_service

    reset_embedding_service()
