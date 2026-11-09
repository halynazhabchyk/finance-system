"""Agent Card of report-agent – the consumer side (Report Service consumes events from RabbitMQ)."""

from __future__ import annotations

from a2a.types import AgentCard

from shared.ai_tools.a2a.card import SkillDescription, build_agent_card

AGENT_NAME = "report-agent"
AGENT_VERSION = "1.0.0"

ANALYZE_MONTHLY_SPENDING = "analyze_monthly_spending"
DETECT_LIMIT_EXCEEDANCES = "detect_limit_exceedances"
COMPARE_PERIODS = "compare_periods"
REGISTER_EXPENSE_AND_REPORT = "register_expense_and_report"

SKILLS = (
    SkillDescription(
        id=ANALYZE_MONTHLY_SPENDING,
        name="Analyse monthly spending",
        description=(
            "Monthly report by categories (totals, remaining amount, shares) from Report Service with a short "
            "explanation. Input: data {year, month, explain?} or a free-text question about spending."
        ),
        tags=["report", "analysis", "consumer"],
        examples=[
            '{"skill_id": "analyze_monthly_spending", "arguments": {"year": 2026, "month": 11}}',
            "На що я найбільше витратив у листопаді 2026?",
        ],
    ),
    SkillDescription(
        id=DETECT_LIMIT_EXCEEDANCES,
        name="Detect limit exceedances",
        description="Categories of a month whose limit is exceeded, with the overrun amount. Input: data {year, month, explain?}.",
        tags=["limits", "overspending", "consumer"],
        examples=['{"skill_id": "detect_limit_exceedances", "arguments": {"year": 2026, "month": 11}}'],
        input_modes=("application/json",),
    ),
    SkillDescription(
        id=COMPARE_PERIODS,
        name="Compare two months",
        description=(
            "Expenses of two months per category with the change between them (computed by the agent's code "
            "from Report Service data, not by the model). Input: data {first: {year, month}, second: {year, month}, explain?}."
        ),
        tags=["comparison", "trend", "consumer"],
        examples=[
            '{"skill_id": "compare_periods", "arguments": {"first": {"year": 2026, "month": 10}, "second": {"year": 2026, "month": 11}}}'
        ],
        input_modes=("application/json",),
    ),
    SkillDescription(
        id=REGISTER_EXPENSE_AND_REPORT,
        name="Add an expense and show the updated report",
        description=(
            "Delegates 'register_expense' to budget-agent over A2A, follows that task until the SAGA ends, then "
            "returns the updated monthly report. If the SAGA is cancelled, reports the reason (DLQ or TIMEOUT). "
            "Input: data {budget_id, category_id, amount, occurred_at, description?}."
        ),
        tags=["a2a", "orchestration", "saga", "report"],
        examples=[
            '{"skill_id": "register_expense_and_report", "arguments": {"budget_id": "<uuid>", "category_id": "<uuid>", '
            '"amount": "250.00", "occurred_at": "2026-11-08"}}'
        ],
        input_modes=("application/json",),
    ),
)

DESCRIPTION = (
    "Consumer agent of the finance system. Works on top of the Report Service REST API (a read model built "
    "from RabbitMQ events) with the user's JWT, and talks to budget-agent over A2A to register expenses."
)


def build_report_agent_card(public_url: str) -> AgentCard:
    return build_agent_card(
        name=AGENT_NAME,
        description=DESCRIPTION,
        version=AGENT_VERSION,
        public_url=public_url + "/",
        skills=SKILLS,
    )
