"""Wiring of report-agent skills into the shared ``SkillExecutor``."""

from __future__ import annotations

from collections.abc import Callable

from shared.ai_tools.a2a.server import SkillExecutor
from shared.ai_tools.gateway.factory import ApiClientFactory
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.llm import LLMClient

from app.a2a_server.agent_card import (
    AGENT_NAME,
    ANALYZE_MONTHLY_SPENDING,
    COMPARE_PERIODS,
    DETECT_LIMIT_EXCEEDANCES,
    REGISTER_EXPENSE_AND_REPORT,
)
from app.services.explainer import Explainer
from app.skills.analysis import AnalysisSkills
from app.skills.register_expense_and_report import RegisterExpenseAndReportSkill, RemoteAgentFactory


def build_executor(
    *,
    api_client_factory: ApiClientFactory,
    remote_factory: RemoteAgentFactory,
    llm_factory: Callable[[], LLMClient | None],
    limits: AgentLimits,
) -> SkillExecutor:
    explainer = Explainer(llm_factory=llm_factory, limits=limits)
    analysis = AnalysisSkills(explainer=explainer, llm_factory=llm_factory, limits=limits)
    return SkillExecutor(
        agent_name=AGENT_NAME,
        skills={
            ANALYZE_MONTHLY_SPENDING: analysis.analyze_monthly_spending,
            DETECT_LIMIT_EXCEEDANCES: analysis.detect_limit_exceedances,
            COMPARE_PERIODS: analysis.compare_periods,
            REGISTER_EXPENSE_AND_REPORT: RegisterExpenseAndReportSkill(remote_factory=remote_factory, explainer=explainer),
        },
        api_client_factory=api_client_factory,
        limits=limits,
        default_text_skill=ANALYZE_MONTHLY_SPENDING,
    )
