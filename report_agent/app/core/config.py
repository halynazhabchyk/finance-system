"""Settings of report-agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from shared.ai_tools.config import AgentLimits, GatewaySettings, LLMSettings, optional_llm_settings


@dataclass(frozen=True)
class ReportAgentSettings:
    public_url: str
    gateway: GatewaySettings
    limits: AgentLimits
    llm: LLMSettings | None
    budget_agent_url: str
    a2a_timeout_seconds: float


@lru_cache
def get_settings() -> ReportAgentSettings:
    gateway = GatewaySettings.from_env()
    return ReportAgentSettings(
        public_url=os.getenv("A2A_PUBLIC_URL", "http://localhost:8080/agents/report").rstrip("/"),
        gateway=gateway,
        limits=AgentLimits.from_env(),
        llm=optional_llm_settings(),
        # budget-agent is reached through Traefik like any other part of the system.
        budget_agent_url=os.getenv("BUDGET_AGENT_URL", f"{gateway.base_url}/agents/budget").rstrip("/"),
        a2a_timeout_seconds=float(os.getenv("A2A_TIMEOUT_SECONDS", "90")),
    )
