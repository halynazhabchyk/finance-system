import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from shared.errors import BusinessRuleError, ConflictError, NotFoundError


def test_category_limit_cannot_exceed_budget(monkeypatch, db):
    from app.repositories import budgets as repository
    from app.services import categories

    budget = SimpleNamespace(total_amount=100)
    monkeypatch.setattr(categories, "budget_or_404", lambda *args, **kwargs: budget)
    monkeypatch.setattr(repository, "category_limits_total", lambda db, budget_id: 80)
    payload = SimpleNamespace(
        limit_amount=25,
        model_dump=lambda: {"name": "Food", "limit_amount": 25},
    )

    with pytest.raises(BusinessRuleError):
        categories.create_category(db, uuid.uuid4(), uuid.uuid4(), payload)
    assert db.rollbacks == 1
    assert db.commits == 0


def test_expense_date_must_be_inside_budget_period(monkeypatch, db):
    from app.repositories import budgets as repository
    from app.services import expenses

    budget = SimpleNamespace(
        budget_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    monkeypatch.setattr(expenses, "budget_or_404", lambda *args, **kwargs: budget)
    monkeypatch.setattr(repository, "get_category", lambda db, budget_id, category_id: object())
    payload = SimpleNamespace(category_id=uuid.uuid4(), occurred_at=date(2026, 2, 1))

    with pytest.raises(BusinessRuleError):
        expenses.create_expense(db, uuid.uuid4(), uuid.uuid4(), payload)
    assert db.rollbacks == 1


def test_foreign_budget_looks_like_missing(monkeypatch, db):
    from app.repositories import budgets as repository
    from app.services.common import budget_or_404

    owner = uuid.uuid4()
    monkeypatch.setattr(
        repository,
        "get_budget",
        lambda db, budget_id, **kwargs: SimpleNamespace(user_id=owner),
    )

    with pytest.raises(NotFoundError):
        budget_or_404(db, uuid.uuid4(), uuid.uuid4())


def test_period_must_be_one_calendar_month():
    from app.services.common import validate_period

    validate_period(date(2026, 2, 1), date(2026, 2, 28))
    with pytest.raises(BusinessRuleError):
        validate_period(date(2026, 2, 1), date(2026, 3, 31))


def test_database_errors_become_service_unavailable(db):
    from sqlalchemy.exc import OperationalError

    from shared.errors import ServiceUnavailableError
    from app.db.transaction import write_transaction

    with pytest.raises(ServiceUnavailableError) as error:
        with write_transaction(db):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    assert error.value.detail == "The budget database is temporarily unavailable."
    assert db.rollbacks == 1
    assert db.commits == 0


def test_unique_violation_becomes_conflict(db):
    from sqlalchemy.exc import IntegrityError

    from app.db.transaction import commit

    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name="uq_budgets_user_period"))

    def failing_commit():
        raise IntegrityError("INSERT", {}, orig)

    db.commit = failing_commit

    with pytest.raises(ConflictError) as error:
        commit(db)

    assert error.value.detail == "A budget already exists for this user and calendar month."
    assert db.rollbacks == 1


def test_unique_violation_on_flush_becomes_conflict(db):
    """A duplicate budget is detected by flush() inside the block, not by commit()."""
    from sqlalchemy.exc import IntegrityError

    from app.db.transaction import write_transaction

    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name="uq_budgets_user_period"))

    with pytest.raises(ConflictError) as error:
        with write_transaction(db):
            raise IntegrityError("INSERT", {}, orig)

    assert error.value.detail == "A budget already exists for this user and calendar month."
    assert db.rollbacks == 1
    assert db.commits == 0


def test_partial_update_rejects_explicit_null():
    from pydantic import ValidationError

    from app.schemas import CategoryUpdate, ExpenseUpdate

    with pytest.raises(ValidationError):
        CategoryUpdate(limit_amount=None)
    with pytest.raises(ValidationError):
        ExpenseUpdate()
    assert ExpenseUpdate(description=None).description is None
    assert ExpenseUpdate(amount=Decimal("1.00"), description="  ").description is None
