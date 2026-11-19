"""Common provider interface - what every AI backend must implement.

WHAT THIS FILE DOES
    Defines AIProvider: the contract shared by Gemini, OpenRouter,
    Ollama and Mock. The high-level operations (analyze_document,
    summarize_document, answer_question, generate_structured) are
    implemented ONCE here on top of the single abstract method
    `_generate()`, so document business logic is never duplicated
    across providers.

    Each concrete provider only:
      1. talks to its own SDK / HTTP API in `_generate()`
      2. reports its configuration state (is_configured / current_model)
      3. performs a lightweight connectivity check (check_connection)

WHY IT EXISTS
    The provider manager operates exclusively on this interface, which
    is what makes automatic fallback possible: it can hand the SAME
    logical operation to a different provider without any endpoint
    knowing about the switch.

HOW IT CONNECTS
    provider_manager.execute("analyze_document", call)
        -> call(provider) invokes these methods
        -> gemini_provider / openrouter_provider / ollama_provider /
           mock_provider implement _generate()
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.services.ai.prompts import (
    ANALYSIS_INSTRUCTION,
    CHAT_INSTRUCTION,
    RAG_INSTRUCTION,
    SUMMARIZE_INSTRUCTION,
)
from app.services.ai.response_validator import extract_json_object, validate_answer


@dataclass
class ProviderResult:
    """Normalized result of one provider call.

    `data` is a str for text operations and a dict for structured ones.
    `usage` carries token counts when the provider reports them.
    """

    data: Any
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Base class every provider derives from."""

    #: machine name used in config/logs ("gemini", "openrouter"...)
    name: str = "provider"
    #: human label for notifications ("Google Gemini")
    label: str = "Provider"
    #: where inference runs: "cloud" | "local" | "simulated"
    inference: str = "cloud"
    #: whether _generate() can request a JSON response format
    supports_json_mode: bool = True

    # --- Provider identity / configuration ----------------------------
    @abstractmethod
    def is_configured(self) -> bool:
        """True when this provider has everything it needs (keys, model)."""

    @abstractmethod
    def current_model(self) -> str:
        """The model id this provider would use right now."""

    @abstractmethod
    def check_connection(self) -> tuple[bool, str]:
        """Lightweight, safe connectivity check. Never leaks secrets."""

    def configuration_detail(self) -> str:
        """Why this provider is not configured (safe for the health API)."""
        return f"{self.label} is not configured."

    @abstractmethod
    def _generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> ProviderResult:
        """Send `prompt` to the provider and return a normalized result.

        Implementations must translate their SDK/HTTP failures into the
        typed errors from ai_exceptions.py.
        """

    # --- Shared high-level operations ----------------------------------
    def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> ProviderResult:
        """Free-form text generation."""
        return self._generate(prompt, system=system, temperature=temperature, json_mode=False)

    def generate_structured(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.1
    ) -> ProviderResult:
        """Ask for JSON and return it as a dict (validated shape comes later)."""
        result = self._generate(
            prompt, system=system, temperature=temperature, json_mode=self.supports_json_mode
        )
        result.data = extract_json_object(result.data)
        return result

    def analyze_document(self, text: str) -> ProviderResult:
        """Full document analysis -> dict matching the AIAnalysis schema.

        JSON extraction happens here so a fenced/messy reply from any
        provider is repaired before validation. Schema validation is
        done by the caller (ai_service) with the existing Pydantic gate.
        """
        prompt = f"{ANALYSIS_INSTRUCTION}\n\nDOCUMENT TEXT:\n{text}"
        return self.generate_structured(prompt, temperature=0.1)

    def summarize_document(self, text: str) -> ProviderResult:
        """Plain-text summary of a document."""
        prompt = f"{SUMMARIZE_INSTRUCTION}\n\nDOCUMENT TEXT:\n{text}"
        return self.generate_text(prompt, temperature=0.3)

    def answer_question(self, document_text: str, question: str) -> ProviderResult:
        """Answer a question using only the supplied document context.

        `document_text` may be the full document or the RAG excerpt
        block - both are framed as untrusted data by CHAT_INSTRUCTION.
        """
        prompt = f"{CHAT_INSTRUCTION}\n\nDOCUMENT TEXT:\n{document_text}\n\nQUESTION: {question}"
        return self.generate_text(prompt, temperature=0.2)

    def answer_with_excerpts(self, excerpts: str, question: str) -> ProviderResult:
        """RAG answer: only the retrieved excerpts may be used."""
        prompt = (
            f"{RAG_INSTRUCTION}\n\nRETRIEVED EXCERPTS:\n{excerpts}\n\nQUESTION: {question}"
        )
        return self.generate_text(prompt, temperature=0.2)

    def _validated_answer(self, result: ProviderResult) -> ProviderResult:
        """Helper for providers: bound and trim the returned answer."""
        result.data = validate_answer(result.data)
        return result
