"""In-memory imitation of the public REST API (Traefik -> User/Budget/Report Service).

Response bodies follow the real contracts (BudgetResponse, BudgetSummary,
CategoryResponse, ExpenseResponse, SagaResponse, MonthlyReportResponse), so the
tools and projections are tested against the same shapes as on the stand.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import jwt

TEST_JWT_SECRET = "test-secret-key-with-at-least-32-bytes!"


def make_jwt(user_id: uuid.UUID) -> str:
    return jwt.encode({"sub": str(user_id)}, TEST_JWT_SECRET, algorithm="HS256")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FakeFinanceApi:
    """State of one user's data plus a log of every HTTP request received."""

    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_active: bool = True
    currency: str = "UAH"
    budgets: dict[str, dict[str, Any]] = field(default_factory=dict)
    categories: dict[str, dict[str, Any]] = field(default_factory=dict)
    expenses: dict[str, dict[str, Any]] = field(default_factory=dict)
    sagas: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    fail_with: int | None = None
    saga_outcome: str = "COMPLETED"  # COMPLETED | CANCELLED (DLQ) after the first status poll

    @property
    def token(self) -> str:
        return make_jwt(self.user_id)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    # --- seeding --------------------------------------------------------

    def add_budget(self, period: str, total: str = "10000.00") -> str:
        year, month = (int(part) for part in period.split("-"))
        budget_id = str(uuid.uuid4())
        self.budgets[budget_id] = {
            "budget_id": budget_id,
            "user_id": str(self.user_id),
            "period_start": f"{year:04d}-{month:02d}-01",
            "period_end": f"{year:04d}-{month:02d}-28",
            "total_amount": total,
            "currency": self.currency,
            "created_at": _now(),
        }
        return budget_id

    def add_category(self, budget_id: str, name: str, limit: str, used: str = "0.00") -> str:
        category_id = str(uuid.uuid4())
        self.categories[category_id] = {
            "category_id": category_id,
            "budget_id": budget_id,
            "name": name,
            "limit_amount": limit,
            "currency": self.currency,
            "_used": Decimal(used),
        }
        return category_id

    def add_report(self, year: int, month: int, categories: list[tuple[str, str, str, str]], total_budget: str = "10000.00") -> None:
        """categories: (name, limit, total_expenses, percentage)."""
        total_expenses = sum((Decimal(item[2]) for item in categories), Decimal("0"))
        self.reports[(year, month)] = {
            "report_id": str(uuid.uuid4()),
            "user_id": str(self.user_id),
            "period": f"{year:04d}-{month:02d}",
            "month": month,
            "period_start": f"{year:04d}-{month:02d}-01",
            "total_budget": total_budget,
            "total_expenses": str(total_expenses),
            "remaining": str(Decimal(total_budget) - total_expenses),
            "remaining_amount": str(Decimal(total_budget) - total_expenses),
            "currency": self.currency,
            "generated_at": _now(),
            "refreshed_at": _now(),
            "categories": [
                {"category_name": name, "limit_amount": limit, "total_expenses": spent, "currency": self.currency, "percentage": share}
                for name, limit, spent, share in categories
            ],
        }

    def paths(self) -> list[str]:
        return [f"{request.method} {request.url.path}" for request in self.requests]

    # --- request handling ----------------------------------------------

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with is not None:
            return httpx.Response(self.fail_with, json={"detail": "Simulated failure."})
        if request.headers.get("Authorization") != f"Bearer {self.token}":
            return httpx.Response(401, json={"detail": "Invalid access token."})

        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else {}
        for pattern, verb, handler in self._routes():
            match = re.fullmatch(pattern, path)
            if match and verb == method:
                return handler(request, body, *match.groups())
        return httpx.Response(404, json={"detail": "Not Found"})

    def _routes(self):
        uuid_re = r"([0-9a-f-]{36})"
        return [
            (rf"/api/users/{uuid_re}", "GET", self._get_user),
            (r"/api/budgets", "GET", self._list_budgets),
            (r"/api/budgets", "POST", self._create_budget),
            (rf"/api/budgets/{uuid_re}", "GET", self._get_summary),
            (rf"/api/budgets/{uuid_re}/categories", "POST", self._create_category),
            (rf"/api/budgets/{uuid_re}/expenses", "POST", self._create_expense),
            (rf"/api/budgets/{uuid_re}/expenses/{uuid_re}", "PATCH", self._update_expense),
            (rf"/api/budgets/{uuid_re}/expenses/{uuid_re}", "DELETE", self._delete_expense),
            (rf"/api/budgets/{uuid_re}/expenses/{uuid_re}/saga", "GET", self._get_saga),
            (r"/api/reports/monthly/(\d+)/(\d+)", "GET", self._monthly_report),
            (r"/api/reports/annual/(\d+)", "GET", self._annual_report),
        ]

    def _get_user(self, _, __, user_id):
        if user_id != str(self.user_id):
            return httpx.Response(403, json={"detail": "The token does not authorize access to this user."})
        return httpx.Response(200, json={"user_id": user_id, "user_name": "Test", "email": "t@example.com", "created_at": _now(), "is_active": self.user_active})

    def _list_budgets(self, request, _):
        period = request.url.params.get("period")
        items = [b for b in self.budgets.values() if period is None or b["period_start"].startswith(period)]
        return httpx.Response(200, json=items)

    def _create_budget(self, _, body):
        if not Decimal(str(body.get("total_amount", "0"))) > 0:
            return httpx.Response(422, json={"detail": [{"loc": ["body", "total_amount"], "msg": "Input should be greater than 0"}]})
        budget_id = self.add_budget(body["period_start"][:7], str(body["total_amount"]))
        return httpx.Response(201, json=self.budgets[budget_id])

    def _get_summary(self, _, __, budget_id):
        budget = self.budgets.get(budget_id)
        if budget is None:
            return httpx.Response(404, json={"detail": "Budget was not found."})
        categories = [c for c in self.categories.values() if c["budget_id"] == budget_id]
        used_total = sum((c["_used"] for c in categories), Decimal("0"))
        return httpx.Response(
            200,
            json={
                "budget": budget,
                "used_amount": str(used_total),
                "available_amount": str(Decimal(budget["total_amount"]) - used_total),
                "categories": [
                    {
                        **{k: v for k, v in c.items() if not k.startswith("_")},
                        "used_amount": str(c["_used"]),
                        "available_amount": str(Decimal(c["limit_amount"]) - c["_used"]),
                        "limit_exceeded": c["_used"] > Decimal(c["limit_amount"]),
                    }
                    for c in categories
                ],
                "expenses": [],
                "service": "budget-service",
                "instance_id": "budget-1",
            },
        )

    def _create_category(self, _, body, budget_id):
        if budget_id not in self.budgets:
            return httpx.Response(404, json={"detail": "Budget was not found."})
        if any(c["budget_id"] == budget_id and c["name"].lower() == body["name"].lower() for c in self.categories.values()):
            return httpx.Response(409, json={"detail": "Category with this name already exists."})
        category_id = self.add_category(budget_id, body["name"], str(body["limit_amount"]))
        return httpx.Response(201, json={k: v for k, v in self.categories[category_id].items() if not k.startswith("_")})

    def _create_expense(self, _, body, budget_id):
        if budget_id not in self.budgets:
            return httpx.Response(404, json={"detail": "Budget was not found."})
        if body["category_id"] not in self.categories:
            return httpx.Response(404, json={"detail": "Category was not found."})
        expense_id, saga_id = str(uuid.uuid4()), str(uuid.uuid4())
        expense = {
            "expense_id": expense_id,
            "budget_id": budget_id,
            "category_id": body["category_id"],
            "amount": str(body["amount"]),
            "currency": self.currency,
            "occurred_at": body["occurred_at"],
            "description": body.get("description"),
            "saga_status": "PENDING",
            "created_at": _now(),
        }
        self.expenses[expense_id] = expense
        self.sagas[expense_id] = {"saga_id": saga_id, "polls": 0}
        return httpx.Response(201, json=expense)

    def _update_expense(self, _, body, budget_id, expense_id):
        expense = self.expenses.get(expense_id)
        if expense is None or expense["budget_id"] != budget_id:
            return httpx.Response(404, json={"detail": "Expense was not found."})
        if expense["saga_status"] != "CONFIRMED":
            return httpx.Response(409, json={"detail": "Only confirmed expenses can be changed."})
        expense.update({key: str(value) for key, value in body.items() if value is not None})
        return httpx.Response(200, json=expense)

    def _delete_expense(self, _, __, budget_id, expense_id):
        expense = self.expenses.get(expense_id)
        if expense is None or expense["budget_id"] != budget_id:
            return httpx.Response(404, json={"detail": "Expense was not found."})
        if expense["saga_status"] != "CONFIRMED":
            return httpx.Response(409, json={"detail": "Only confirmed expenses can be deleted."})
        del self.expenses[expense_id]
        return httpx.Response(204)

    def _get_saga(self, _, __, budget_id, expense_id):
        expense = self.expenses.get(expense_id)
        if expense is None:
            return httpx.Response(404, json={"detail": "Expense was not found."})
        saga = self.sagas[expense_id]
        saga["polls"] += 1
        status, reason = "STARTED", None
        if saga["polls"] >= 2:
            status = self.saga_outcome
            expense["saga_status"] = "CONFIRMED" if status == "COMPLETED" else "CANCELLED"
            reason = "DLQ" if status == "CANCELLED" else None
        return httpx.Response(
            200,
            json={
                "saga_id": saga["saga_id"],
                "saga_type": "CreateExpense",
                "aggregate_type": "Expense",
                "aggregate_id": expense_id,
                "status": status,
                "current_step": "DONE" if status != "STARTED" else "WAIT_REPORT",
                "started_at": _now(),
                "deadline_at": _now(),
                "finished_at": _now() if status != "STARTED" else None,
                "failure_reason": reason,
                "failure_details": "Report Service rejected the event." if reason else None,
                "compensation_attempts": 0,
                "last_error": None,
            },
        )

    def _monthly_report(self, _, __, year, month):
        report = self.reports.get((int(year), int(month)))
        if report is None:
            return httpx.Response(404, json={"detail": "Monthly report is not available yet."})
        return httpx.Response(200, json=report)

    def _annual_report(self, _, __, year):
        months = [r for (y, _m), r in sorted(self.reports.items()) if y == int(year)]
        if not months:
            return httpx.Response(404, json={"detail": "Annual report is not available yet."})
        total_budget = sum((Decimal(m["total_budget"]) for m in months), Decimal("0"))
        total_expenses = sum((Decimal(m["total_expenses"]) for m in months), Decimal("0"))
        return httpx.Response(
            200,
            json={
                "report_id": str(uuid.uuid4()),
                "user_id": str(self.user_id),
                "period": str(year),
                "year": int(year),
                "total_budget": str(total_budget),
                "total_expenses": str(total_expenses),
                "remaining": str(total_budget - total_expenses),
                "remaining_amount": str(total_budget - total_expenses),
                "currency": self.currency,
                "generated_at": _now(),
                "months": months,
            },
        )
