"""Ollama provider - optional LOCAL inference for open-weight models.

WHAT THIS FILE DOES
    Talks to the local Ollama HTTP API (default http://localhost:11434)
    with a configurable model such as qwen2.5:1.5b or llama3.2:1b.
    No API key, no cloud, no GPU required.

WHY IT EXISTS
    When cloud inference is unavailable, a lightweight Hugging Face
    open-weight model running through Ollama keeps the application
    usable. The local model is OPTIONAL: Ollama being absent never
    prevents application startup - the manager simply skips it.

HOW IT CONNECTS
    provider_manager -> POST {OLLAMA_BASE_URL}/api/chat (only when
        OLLAMA_ENABLED=true AND OLLAMA_MODEL is set)
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.services.ai.ai_exceptions import (
    ConnectionFailedError,
    InvalidResponseError,
    ModelNotFoundError,
    ProviderTimeoutError,
    classify_status_code,
)
from app.services.ai.provider_interface import AIProvider, ProviderResult

_BODY_SNIPPET_LIMIT = 300


class OllamaProvider(AIProvider):
    """Local inference through the Ollama runtime."""

    name = "ollama"
    label = "Ollama (local)"
    inference = "local"
    supports_json_mode = True  # Ollama's format="json" is widely supported

    # --- Configuration ---------------------------------------------------
    def is_configured(self) -> bool:
        return bool(settings.OLLAMA_ENABLED) and bool(settings.OLLAMA_MODEL.strip())

    def current_model(self) -> str:
        return settings.OLLAMA_MODEL.strip() or "-"

    def configuration_detail(self) -> str:
        if not settings.OLLAMA_ENABLED:
            return "Ollama is disabled (OLLAMA_ENABLED=false)."
        if not settings.OLLAMA_MODEL.strip():
            return "OLLAMA_MODEL is not set."
        return "Ollama is not configured."

    def _base_url(self) -> str:
        return settings.OLLAMA_BASE_URL.rstrip("/")

    # --- Transport -------------------------------------------------------
    def _generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> ProviderResult:
        if not self.is_configured():
            # Not configured -> the manager skips us; defensive here.
            raise ConnectionFailedError("Ollama is not enabled (OLLAMA_ENABLED=false).")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.current_model(),
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode and self.supports_json_mode:
            payload["format"] = "json"

        try:
            response = httpx.post(
                f"{self._base_url()}/api/chat",
                json=payload,
                timeout=settings.AI_REQUEST_TIMEOUT,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Ollama request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ConnectionFailedError(
                f"Ollama is not reachable at {self._base_url()}."
            ) from exc

        if response.status_code == 404:
            # Either the route or - more commonly - the model is missing.
            body = response.text[:_BODY_SNIPPET_LIMIT].lower()
            if "model" in body or not body:
                raise ModelNotFoundError(
                    f"Ollama model '{self.current_model()}' is not installed. "
                    f"Run: ollama pull {self.current_model()}"
                )
            raise classify_status_code(404, response.text[:_BODY_SNIPPET_LIMIT])
        if response.status_code >= 400:
            raise classify_status_code(
                response.status_code, response.text[:_BODY_SNIPPET_LIMIT]
            )

        try:
            data = response.json()
            content = data["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidResponseError("Ollama returned a malformed response.") from exc

        if not isinstance(content, str) or not content.strip():
            raise InvalidResponseError("Ollama returned an empty completion.")

        usage: dict = {}
        if data.get("prompt_eval_count"):
            usage["input_tokens"] = int(data["prompt_eval_count"])
        if data.get("eval_count"):
            usage["output_tokens"] = int(data["eval_count"])

        return ProviderResult(
            data=content,
            provider=self.name,
            model=self.current_model(),
            usage=usage,
        )

    # --- Health ----------------------------------------------------------
    def check_connection(self) -> tuple[bool, str]:
        """Real check: Ollama reachable AND the model is installed."""
        if not settings.OLLAMA_ENABLED:
            return False, "Ollama is disabled (OLLAMA_ENABLED=false)."
        if not settings.OLLAMA_MODEL.strip():
            return False, "OLLAMA_MODEL is not set."

        try:
            response = httpx.get(f"{self._base_url()}/api/tags", timeout=5.0)
        except httpx.HTTPError:
            return (
                False,
                f"Ollama is not running at {self._base_url()} "
                "(start it with: ollama serve).",
            )
        if response.status_code >= 400:
            return False, "Ollama answered with an error."

        try:
            installed = [
                model.get("name", "")
                for model in response.json().get("models", [])
            ]
        except (ValueError, KeyError, TypeError):
            return False, "Ollama returned an unexpected model list."

        wanted = self.current_model()
        # Ollama lists names with tags: "qwen2.5:1.5b". Match base name too.
        if any(name == wanted or name.split(":")[0] == wanted for name in installed):
            return True, f"Ollama reachable - model '{wanted}' installed."

        return (
            False,
            f"Model '{wanted}' is not installed. Run: ollama pull {wanted}",
        )
