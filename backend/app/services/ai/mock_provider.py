"""Mock AI provider - deterministic, offline, never presented as real.

WHAT THIS FILE DOES
    Wraps the existing deterministic engine (services/mock_ai.py) in the
    shared AIProvider interface so the provider manager can treat it
    exactly like a real backend.

WHY IT EXISTS
    Local development, automated tests and CI run with zero API keys
    and zero cost. Mock answers are always labelled "mock" - they are
    never represented as real model inference.

RULE
    Mock is only ever used when MOCK_AI=true (explicitly enabled).
    It is never appended to the fallback chain automatically.

HOW IT CONNECTS
    provider_manager -> this class (only when MOCK_AI=true)
    mock_ai.py       -> the actual deterministic logic
"""
from __future__ import annotations

from app.core.config import settings
from app.services import mock_ai
from app.services.ai.provider_interface import AIProvider, ProviderResult
from app.services.ai.response_validator import validate_analysis


class MockProvider(AIProvider):
    """Simulated provider backed by regex/rules - no network, no keys."""

    name = "mock"
    label = "Mock AI"
    inference = "simulated"
    supports_json_mode = True

    def is_configured(self) -> bool:
        # The mock is only usable (and allowed into the chain) in mock mode;
        # with MOCK_AI=false it is excluded so it can never become a silent
        # fallback for real providers.
        return bool(settings.MOCK_AI)

    def current_model(self) -> str:
        return "-"  # no model exists; the UI shows this honestly

    def configuration_detail(self) -> str:
        # Shown by /api/health/ai when the mock is NOT part of the chain.
        if settings.MOCK_AI:
            return "Mock AI mode is active - no external API required."
        return (
            "Excluded from the chain (MOCK_AI=false) - never used as a "
            "silent fallback."
        )

    def check_connection(self) -> tuple[bool, str]:
        if settings.MOCK_AI:
            return True, "Mock AI mode is active - no external API required."
        return (
            False,
            "Excluded from the chain (MOCK_AI=false) - never used as a silent fallback.",
        )

    # --- Operations ------------------------------------------------------
    def analyze_document(self, text: str) -> ProviderResult:
        """Deterministic analysis, validated through the same schema."""
        payload = mock_ai.generate_analysis(text)
        return ProviderResult(
            data=validate_analysis(payload),
            provider=self.name,
            model=self.current_model(),
        )

    def answer_question(self, document_text: str, question: str) -> ProviderResult:
        answer = mock_ai.answer_question(document_text, question)
        return ProviderResult(
            data=answer, provider=self.name, model=self.current_model()
        )

    def answer_with_excerpts(self, excerpts: str, question: str) -> ProviderResult:
        """RAG path: score sentences inside the retrieved excerpts."""
        answer = mock_ai.answer_question(excerpts, question)
        return ProviderResult(
            data=answer, provider=self.name, model=self.current_model()
        )

    def summarize_document(self, text: str) -> ProviderResult:
        """Extractive summary - no sleeping, no invented facts."""
        sentences = mock_ai._split_sentences(text)
        summary = mock_ai._build_summary(sentences, text)
        return ProviderResult(
            data=summary, provider=self.name, model=self.current_model()
        )

    def generate_text(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.2
    ) -> ProviderResult:
        """Honest simulated output - always says it is simulated."""
        return ProviderResult(
            data=(
                "[Mock AI] Simulated response: no external model was contacted. "
                "Set MOCK_AI=false with a provider API key for real inference."
            ),
            provider=self.name,
            model=self.current_model(),
        )

    def generate_structured(
        self, prompt: str, *, system: str | None = None, temperature: float = 0.1
    ) -> ProviderResult:
        """Structured mock output is only produced by analyze_document."""
        payload = mock_ai.generate_analysis(prompt)
        return ProviderResult(
            data=validate_analysis(payload),
            provider=self.name,
            model=self.current_model(),
        )

    def _generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> ProviderResult:
        # All public operations are overridden above; _generate exists
        # only to satisfy the interface.
        return self.generate_text(prompt, system=system, temperature=temperature)
