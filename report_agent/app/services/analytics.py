"""Deterministic analytics over service data (no language model).

Requirement 1.6: numbers are never computed by the LLM. Differences between
months and limit overruns are derived here with ``Decimal`` from the amounts
returned by Report Service and Budget Service.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared.ai_tools.tools.projections import money


def limit_exceedances(summary: dict[str, Any]) -> dict[str, Any]:
    budget = summary["budget"]
    currency = budget["currency"]
    exceeded = [
        {
            "category_id": category["category_id"],
            "name": category["name"],
            "limit_amount": money(category["limit_amount"], currency),
            "used_amount": money(category["used_amount"], currency),
            "overrun": money(Decimal(str(category["used_amount"])) - Decimal(str(category["limit_amount"])), currency),
        }
        for category in summary["categories"]
        if category["limit_exceeded"]
    ]
    return {
        "budget_id": budget["budget_id"],
        "period": str(budget["period_start"])[:7],
        "checked_categories": len(summary["categories"]),
        "exceeded_count": len(exceeded),
        "exceeded": exceeded,
    }


def compare_reports(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    currency = second["currency"]
    first_by_name = {item["category_name"]: Decimal(str(item["total_expenses"])) for item in first["categories"]}
    second_by_name = {item["category_name"]: Decimal(str(item["total_expenses"])) for item in second["categories"]}
    names = sorted(set(first_by_name) | set(second_by_name))
    categories = []
    for name in names:
        before, after = first_by_name.get(name, Decimal("0")), second_by_name.get(name, Decimal("0"))
        categories.append(
            {
                "name": name,
                first["period"]: money(before, currency),
                second["period"]: money(after, currency),
                "change": money(after - before, currency),
                "trend": _trend(after - before),
            }
        )
    total_before, total_after = Decimal(str(first["total_expenses"])), Decimal(str(second["total_expenses"]))
    return {
        "first_period": first["period"],
        "second_period": second["period"],
        "total_expenses": {
            first["period"]: money(total_before, currency),
            second["period"]: money(total_after, currency),
            "change": money(total_after - total_before, currency),
            "trend": _trend(total_after - total_before),
        },
        "categories": categories,
        "increased": [item["name"] for item in categories if item["trend"] == "increased"],
    }


def _trend(delta: Decimal) -> str:
    if delta > 0:
        return "increased"
    if delta < 0:
        return "decreased"
    return "unchanged"
