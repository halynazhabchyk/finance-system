import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from shared.errors import BusinessRuleError, NotFoundError


def report(user_id, month, expenses=Decimal("100.00")):
    return SimpleNamespace(
        report_id=uuid.uuid4(),
        user_id=user_id,
        period_start=date(2026, month, 1),
        total_budget=Decimal("1000.00"),
        total_expenses=expenses,
        remaining_amount=Decimal("1000.00") - expenses,
        currency="UAH",
        refreshed_at=datetime(2026, month, 28, tzinfo=timezone.utc),
    )


def category(name, amount):
    return SimpleNamespace(
        category_name=name,
        limit_amount=Decimal("500.00"),
        total_expenses=Decimal(amount),
    )


def test_monthly_report_returns_totals_and_percentages(monkeypatch):
    from app.repositories import reports as repository
    from app.services.reports import get_monthly_report

    user_id = uuid.uuid4()
    item = report(user_id, 1)
    monkeypatch.setattr(repository, "get_month", lambda db, uid, period: item)
    monkeypatch.setattr(repository, "get_categories", lambda db, report_id: [category("Food", "60"), category("Rent", "40")])

    result = get_monthly_report(object(), user_id, 2026, 1)

    assert result["total_budget"] == Decimal("1000.00")
    assert result["total_expenses"] == Decimal("100.00")
    assert result["remaining"] == Decimal("900.00")
    assert sum(item["percentage"] for item in result["categories"]) == Decimal("100.00")
    assert result["period"] == "2026-01"
    assert result["month"] == 1


def test_zero_expenses_returns_zero_percentages(monkeypatch):
    from app.repositories import reports as repository
    from app.services.reports import get_monthly_report

    user_id = uuid.uuid4()
    item = report(user_id, 1, Decimal("0.00"))
    monkeypatch.setattr(repository, "get_month", lambda db, uid, period: item)
    monkeypatch.setattr(repository, "get_categories", lambda db, report_id: [])

    result = get_monthly_report(object(), user_id, 2026, 1)

    assert result["remaining"] == Decimal("1000.00")
    assert result["categories"] == []


def test_category_totals_must_match_report_total(monkeypatch):
    from app.repositories import reports as repository
    from app.services.reports import get_monthly_report

    user_id = uuid.uuid4()
    item = report(user_id, 1, Decimal("100.00"))
    monkeypatch.setattr(repository, "get_month", lambda db, uid, period: item)
    monkeypatch.setattr(repository, "get_categories", lambda db, report_id: [category("Food", "90")])

    with pytest.raises(BusinessRuleError):
        get_monthly_report(object(), user_id, 2026, 1)


def test_annual_report_contains_monthly_statistics(monkeypatch):
    from app.repositories import reports as repository
    from app.services.reports import get_annual_report

    user_id = uuid.uuid4()
    months = [report(user_id, 1), report(user_id, 2, Decimal("200.00"))]
    monkeypatch.setattr(repository, "get_months", lambda db, uid, year: months)
    monkeypatch.setattr(
        repository,
        "get_categories",
        lambda db, report_id: (
            [category("Food", "100")]
            if report_id == months[0].report_id
            else [category("Food", "200")]
        ),
    )

    result = get_annual_report(object(), user_id, 2026)

    assert result["total_budget"] == Decimal("2000.00")
    assert result["total_expenses"] == Decimal("300.00")
    assert result["remaining"] == Decimal("1700.00")
    assert [month["month"] for month in result["months"]] == [1, 2]
    assert result["report_id"]


def test_missing_annual_report_returns_404(monkeypatch):
    from app.repositories import reports as repository
    from app.services.reports import get_annual_report

    monkeypatch.setattr(repository, "get_months", lambda db, uid, year: [])

    with pytest.raises(NotFoundError):
        get_annual_report(object(), uuid.uuid4(), 2026)


def test_missing_monthly_report_returns_404_over_http(client, monkeypatch):
    from app.api.dependencies import get_current_user, get_db
    from app.main import app
    from app.repositories import reports as repository

    monkeypatch.setattr(repository, "get_month", lambda db, uid, period: None)
    app.dependency_overrides[get_current_user] = lambda: uuid.uuid4()
    app.dependency_overrides[get_db] = lambda: iter([object()])
    try:
        response = client.get("/internal/reports/monthly/2026/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Monthly report is not available yet."}
