"""Wiring of budget-agent skills into the shared ``SkillExecutor``."""

from __future__ import annotations

from collections.abc import Callable

from shared.ai_tools.a2a.server import SkillExecutor
from shared.ai_tools.gateway.factory import ApiClientFactory
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.llm import LLMClient

from app.a2a_server.agent_card import AGENT_NAME, CANCEL_OR_UPDATE_EXPENSE, MANAGE_BUDGET, REGISTER_EXPENSE
from app.skills.cancel_or_update_expense import cancel_or_update_expense
from app.skills.manage_budget import manage_budget
from app.skills.register_expense import RegisterExpenseSkill


def build_executor(
    *,
    api_client_factory: ApiClientFactory,
    llm_factory: Callable[[], LLMClient | None],
    limits: AgentLimits,
    saga_wait_seconds: float,
    saga_poll_interval_seconds: float,
    sleep=None,
) -> SkillExecutor:
    return SkillExecutor(
        agent_name=AGENT_NAME,
        skills={
            REGISTER_EXPENSE: RegisterExpenseSkill(
                llm_factory=llm_factory,
                limits=limits,
                saga_wait_seconds=saga_wait_seconds,
                saga_poll_interval_seconds=saga_poll_interval_seconds,
                sleep=sleep,
            ),
            MANAGE_BUDGET: manage_budget,
            CANCEL_OR_UPDATE_EXPENSE: cancel_or_update_expense,
        },
        api_client_factory=api_client_factory,
        limits=limits,
        default_text_skill=REGISTER_EXPENSE,
    )
