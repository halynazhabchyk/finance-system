import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class FakeSession:
    def rollback(self):
        pass


def test_category_limit_cannot_exceed_budget(monkeypatch):
    from app.repositories import budgets as repository
    from app.services.categories import create_category

    budget = SimpleNamespace(total_amount=100)
    monkeypatch.setattr("app.services.categories.budget_or_404", lambda db, budget_id, user_id: budget)
    monkeypatch.setattr(repository, "category_limits_total", lambda db, budget_id: 80)

    with pytest.raises(HTTPException) as error:
        create_category(
            FakeSession(),
            uuid.uuid4(),
            uuid.uuid4(),
            SimpleNamespace(limit_amount=25, model_dump=lambda: {"name": "Food", "limit_amount": 25}),
        )

    assert error.value.status_code == 422


def test_expense_date_must_be_inside_budget_period(monkeypatch):
    from datetime import date

    from app.repositories import budgets as repository
    from app.services.expenses import create_expense

    budget = SimpleNamespace(period_start=date(2026, 1, 1), period_end=date(2026, 1, 31))
    monkeypatch.setattr("app.services.expenses.budget_or_404", lambda db, budget_id, user_id: budget)
    monkeypatch.setattr(repository, "get_category", lambda db, budget_id, category_id: object())

    payload = SimpleNamespace(category_id=uuid.uuid4(), occurred_at=date(2026, 2, 1))
    payload.model_dump = lambda: {"category_id": payload.category_id, "amount": 10, "occurred_at": payload.occurred_at}

    with pytest.raises(HTTPException) as error:
        create_expense(FakeSession(), uuid.uuid4(), uuid.uuid4(), payload)

    assert error.value.status_code == 422
