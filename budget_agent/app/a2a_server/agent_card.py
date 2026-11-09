"""Agent Card of budget-agent – the producer side (Budget Service publishes events via Outbox)."""

from __future__ import annotations

from a2a.types import AgentCard

from shared.ai_tools.a2a.card import SkillDescription, build_agent_card

AGENT_NAME = "budget-agent"
AGENT_VERSION = "1.0.0"

REGISTER_EXPENSE = "register_expense"
MANAGE_BUDGET = "manage_budget"
CANCEL_OR_UPDATE_EXPENSE = "cancel_or_update_expense"

SKILLS = (
    SkillDescription(
        id=REGISTER_EXPENSE,
        name="Register an expense",
        description=(
            "Registers an expense in the user's budget. Budget Service starts the 'CreateExpense' SAGA and "
            "publishes ExpenseCreated through its Outbox. The task stays WORKING while the SAGA runs and ends "
            "COMPLETED (expense CONFIRMED) or FAILED (expense CANCELLED, reason DLQ or TIMEOUT). "
            "Input: data {skill_id, arguments: {budget_id, category_id, amount, occurred_at, description?}} "
            "or free text."
        ),
        tags=["expense", "saga", "ExpenseCreated", "producer"],
        examples=[
            '{"skill_id": "register_expense", "arguments": {"budget_id": "<uuid>", "category_id": "<uuid>", '
            '"amount": "250.00", "occurred_at": "2026-11-08", "description": "Продукти"}}',
            "Додай витрату 250 грн на продукти за 8 листопада 2026",
        ],
    ),
    SkillDescription(
        id=MANAGE_BUDGET,
        name="Manage budget and categories",
        description=(
            "Creates a monthly budget (event BudgetCreated) or a category with a limit (event BudgetUpdated). "
            "Structured input only, no language model: data {skill_id, arguments: {action: create_budget, year, "
            "month, total_amount, currency?} | {action: create_category, budget_id, name, limit_amount}}."
        ),
        tags=["budget", "category", "BudgetCreated", "BudgetUpdated", "producer"],
        examples=[
            '{"skill_id": "manage_budget", "arguments": {"action": "create_budget", "year": 2026, "month": 12, "total_amount": "12000.00"}}',
            '{"skill_id": "manage_budget", "arguments": {"action": "create_category", "budget_id": "<uuid>", "name": "Подарунки", "limit_amount": "1500.00"}}',
        ],
        input_modes=("application/json",),
    ),
    SkillDescription(
        id=CANCEL_OR_UPDATE_EXPENSE,
        name="Change or delete an expense (with confirmation)",
        description=(
            "Changes (event ExpenseUpdated) or deletes (event ExpenseDeleted) a CONFIRMED expense. "
            "Structured input only, no language model. Without \"confirm\": true the task ends INPUT_REQUIRED "
            "with a description of the change; send the same arguments with confirm=true to execute it."
        ),
        tags=["expense", "ExpenseUpdated", "ExpenseDeleted", "confirmation", "producer"],
        examples=[
            '{"skill_id": "cancel_or_update_expense", "arguments": {"action": "delete", "budget_id": "<uuid>", "expense_id": "<uuid>", "confirm": true}}',
            '{"skill_id": "cancel_or_update_expense", "arguments": {"action": "update", "budget_id": "<uuid>", "expense_id": "<uuid>", "changes": {"amount": "300.00"}}}',
        ],
        input_modes=("application/json",),
    ),
)

DESCRIPTION = (
    "Producer agent of the finance system. Works on top of the Budget Service REST API with the user's JWT; "
    "domain events (BudgetCreated, BudgetUpdated, ExpenseCreated, ExpenseUpdated, ExpenseDeleted) are still "
    "created only by Budget Service through its Transactional Outbox and RabbitMQ."
)


def build_budget_agent_card(public_url: str) -> AgentCard:
    return build_agent_card(
        name=AGENT_NAME,
        description=DESCRIPTION,
        version=AGENT_VERSION,
        public_url=public_url + "/",
        skills=SKILLS,
    )
