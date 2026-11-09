"""Which agents the client can talk to and where the gateway is."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTarget:
    name: str
    path: str  # gateway prefix of the agent (Traefik route)
    text_skill: str  # skill that handles free text; it must be declared in the Agent Card
    hint: str


AGENTS: dict[str, AgentTarget] = {
    "budget": AgentTarget(
        name="budget-agent",
        path="/agents/budget",
        text_skill="register_expense",
        hint="Producer: реєстрація витрат природною мовою, напр. «Додай витрату 250 грн на продукти за 8 листопада 2026».",
    ),
    "report": AgentTarget(
        name="report-agent",
        path="/agents/report",
        text_skill="analyze_monthly_spending",
        hint="Consumer: питання про витрати, напр. «На що я найбільше витратила в листопаді 2026?».",
    ),
}

DEFAULT_GATEWAY_URL = "http://localhost:8080"
# Longer than the SAGA wait of budget-agent (A2A_SAGA_WAIT_SECONDS, 45 s) plus model calls.
DEFAULT_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class ChatSettings:
    gateway_url: str
    target: AgentTarget
    email: str | None
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @property
    def agent_url(self) -> str:
        return self.gateway_url + self.target.path

    @classmethod
    def build(cls, agent: str, gateway_url: str | None, email: str | None) -> ChatSettings:
        url = (gateway_url or os.getenv("GATEWAY_URL") or DEFAULT_GATEWAY_URL).rstrip("/")
        return cls(gateway_url=url, target=AGENTS[agent], email=email)
