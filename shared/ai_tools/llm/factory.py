"""Choice of the ``LLMClient`` implementation by ``LLM_PROVIDER``."""

from __future__ import annotations

from shared.ai_tools.config import ConfigurationError, LLMSettings
from shared.ai_tools.llm.client import LLMClient


def create_llm_client(settings: LLMSettings) -> LLMClient:
    """Build the adapter for the configured provider (import is lazy: only it needs the SDK)."""
    if settings.provider == "gemini":
        from shared.ai_tools.llm.gemini import GeminiLLMClient

        return GeminiLLMClient(settings)
    raise ConfigurationError(f"Unsupported LLM_PROVIDER: {settings.provider!r}.")
