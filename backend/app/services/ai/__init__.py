"""Modular multi-provider AI package.

Layout
    ai_exceptions.py     typed errors + retry/fallback classification
    prompts.py           provider-independent prompt templates
    response_validator.py  JSON extraction + schema validation
    provider_interface.py  the contract every provider implements
    gemini_provider.py   Google Gemini (primary cloud AI)
    openrouter_provider.py  OpenRouter (cloud fallback, free-only guard)
    ollama_provider.py   Ollama (optional local inference)
    mock_provider.py     deterministic offline engine (dev/tests/CI)
    provider_manager.py  selection, retries, fallback, notices
    execution_log.py     honest per-request metrics for /api/health/ai
    embedding_service.py independent embedding providers for RAG
"""
from app.services.ai.ai_exceptions import AIProviderError
from app.services.ai.embedding_service import (
    EmbeddingResult,
    get_embedding_service,
    reset_embedding_service,
)
from app.services.ai.execution_log import ExecutionLog, execution_log
from app.services.ai.provider_interface import AIProvider, ProviderResult
from app.services.ai.provider_manager import (
    ExecutionOutcome,
    ProviderManager,
    build_provider_chain,
    get_provider_manager,
    parse_priority,
    reset_provider_manager,
)

__all__ = [
    "AIProvider",
    "AIProviderError",
    "EmbeddingResult",
    "ExecutionLog",
    "ExecutionOutcome",
    "ProviderManager",
    "ProviderResult",
    "build_provider_chain",
    "execution_log",
    "get_embedding_service",
    "get_provider_manager",
    "parse_priority",
    "reset_embedding_service",
    "reset_provider_manager",
]
