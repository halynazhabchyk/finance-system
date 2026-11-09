"""Settings of budget-agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from shared.ai_tools.config import AgentLimits, GatewaySettings, LLMSettings, optional_llm_settings


@dataclass(frozen=True)
class BudgetAgentSettings:
    public_url: str
    gateway: GatewaySettings
    limits: AgentLimits
    llm: LLMSettings | None
    saga_wait_seconds: float
    saga_poll_interval_seconds: float


@lru_cache
def get_settings() -> BudgetAgentSettings:
    return BudgetAgentSettings(
        public_url=os.getenv("A2A_PUBLIC_URL", "http://localhost:8080/agents/budget").rstrip("/"),
        gateway=GatewaySettings.from_env(),
        limits=AgentLimits.from_env(),
        llm=optional_llm_settings(),
        # Longer than SAGA_TIMEOUT_SECONDS (30 s) + one watcher interval, so TIMEOUT compensation is observed.
        saga_wait_seconds=float(os.getenv("A2A_SAGA_WAIT_SECONDS", "45")),
        saga_poll_interval_seconds=float(os.getenv("A2A_SAGA_POLL_INTERVAL_SECONDS", "1")),
    )
