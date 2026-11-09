"""Minimal tool results for the model (requirement 2.3).

Only identifiers, names, amounts with currency and statuses are kept. Service
fields (``instance_id``, ``created_at``), the owner's ``user_id`` and the list
of individual expenses are dropped: the model does not need them and every
extra field costs tokens.

All numbers come from the services; nothing is computed here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

SAGA_PENDING_NOTE = (
    "The expense was accepted with saga_status PENDING. It will be included in the "
    "monthly report and limits only after the SAGA confirms it (usually within seconds; "
    "if the report service fails, the expense is cancelled automatically). Tell the user this."
)


def money(amount: Any, currency: str) -> str:
    return f"{Decimal(str(amount)):.2f} {currency}"


def budget_reference(budget: dict[str, Any]) -> dict[str, Any]:
    currency = budget["currency"]
    return {
        "budget_id": budget["budget_id"],
        "period": str(budget["period_start"])[:7],
        "total_amount": money(budget["total_amount"], currency),
    }


def found_budget(budgets: list[dict[str, Any]], period: str) -> dict[str, Any]:
    if not budgets:
        return {
            "found": False,
            "period": period,
            "message": f"The user has no budget for {period}. Budgets are created by the user "
            "directly in the API; the assistant cannot create them.",
        }
    return {"found": True, "budget": budget_reference(budgets[0])}


def budget_by_categories(summary: dict[str, Any]) -> dict[str, Any]:
    budget = summary["budget"]
    currency = budget["currency"]
    return {
        **budget_reference(budget),
        "used_amount": money(summary["used_amount"], currency),
        "available_amount": money(summary["available_amount"], currency),
        "categories": [
            {
                "category_id": category["category_id"],
                "name": category["name"],
                "limit_amount": money(category["limit_amount"], currency),
                "used_amount": money(category["used_amount"], currency),
                "available_amount": money(category["available_amount"], currency),
                "limit_exceeded": category["limit_exceeded"],
            }
            for category in summary["categories"]
        ],
    }


def created_category(category: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "created",
        "category_id": category["category_id"],
        "budget_id": category["budget_id"],
        "name": category["name"],
        "limit_amount": money(category["limit_amount"], category["currency"]),
    }


def created_expense(expense: dict[str, Any]) -> dict[str, Any]:
    result = {
        "status": "accepted",
        "expense_id": expense["expense_id"],
        "budget_id": expense["budget_id"],
        "category_id": expense["category_id"],
        "amount": money(expense["amount"], expense["currency"]),
        "occurred_at": expense["occurred_at"],
        "saga_status": expense["saga_status"],
    }
    if expense["saga_status"] == "PENDING":
        result["note"] = SAGA_PENDING_NOTE
    return result


def monthly_report(report: dict[str, Any]) -> dict[str, Any]:
    currency = report["currency"]
    return {
        "period": report["period"],
        "total_budget": money(report["total_budget"], currency),
        "total_expenses": money(report["total_expenses"], currency),
        "remaining": money(report["remaining"], currency),
        "categories": [
            {
                "name": category["category_name"],
                "limit_amount": money(category["limit_amount"], currency),
                "total_expenses": money(category["total_expenses"], currency),
                "share_of_expenses_percent": f"{Decimal(str(category['percentage'])):.2f}",
            }
            for category in report["categories"]
        ],
    }


def annual_report(report: dict[str, Any]) -> dict[str, Any]:
    currency = report["currency"]
    return {
        "year": report["year"],
        "total_budget": money(report["total_budget"], currency),
        "total_expenses": money(report["total_expenses"], currency),
        "remaining": money(report["remaining"], currency),
        "months": [
            {
                "period": month["period"],
                "total_expenses": money(month["total_expenses"], currency),
                "remaining": money(month["remaining"], currency),
            }
            for month in report["months"]
        ],
    }
