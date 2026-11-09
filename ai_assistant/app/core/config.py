"""Settings of the AI Assistant assembled from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from shared.ai_tools.config import AgentLimits, GatewaySettings, LLMSettings


@dataclass(frozen=True)
class AssistantSettings:
    llm: LLMSettings
    limits: AgentLimits
    gateway: GatewaySettings


@lru_cache
def get_settings() -> AssistantSettings:
    """Read once per process; raises ``ConfigurationError`` if LLM_API_KEY/LLM_MODEL are missing."""
    return AssistantSettings(
        llm=LLMSettings.from_env(),
        limits=AgentLimits.from_env(),
        gateway=GatewaySettings.from_env(),
    )
