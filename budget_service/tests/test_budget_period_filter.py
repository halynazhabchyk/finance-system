"""GET /internal/budgets?period=YYYY-MM – lookup of the budget of one calendar month (ЛР №4, п. 0.1)."""

import uuid
from datetime import date
from types import SimpleNamespace

import pytest


def _budget(user_id: uuid.UUID, period_start: str = "2026-11-01", period_end: str = "2026-11-30"):
    return SimpleNamespace(
        budget_id=uuid.uuid4(),
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
        total_amount="10000.00",
        currency="UAH",
        created_at="2026-11-01T00:00:00Z",
    )


def test_period_query_is_passed_to_service(client, as_user, monkeypatch):
    from app.api.routers import budgets as router_module

    user_id = uuid.uuid4()
    calls = []

    def fake_list(db, uid, *, period=None):
        calls.append((uid, period))
        return [_budget(uid)]

    monkeypatch.setattr(router_module.budget_service, "list_budgets", fake_list)
    as_user(user_id)

    response = client.get("/internal/budgets", params={"period": "2026-11"})

    assert response.status_code == 200
    assert calls == [(user_id, "2026-11")]
    assert len(response.json()) == 1
    assert response.json()[0]["period_start"] == "2026-11-01"


def test_without_period_behaviour_is_unchanged(client, as_user, monkeypatch):
    from app.api.routers import budgets as router_module

    user_id = uuid.uuid4()
    calls = []

    def fake_list(db, uid, *, period=None):
        calls.append(period)
        return [_budget(uid), _budget(uid, "2026-10-01", "2026-10-31")]

    monkeypatch.setattr(router_module.budget_service, "list_budgets", fake_list)
    as_user(user_id)

    response = client.get("/internal/budgets")

    assert response.status_code == 200
    assert calls == [None]
    assert len(response.json()) == 2


@pytest.mark.parametrize("period", ["2026-13", "2026-1", "26-11", "2026/11", "november"])
def test_invalid_period_is_rejected_with_422(client, as_user, period):
    as_user(uuid.uuid4())

    response = client.get("/internal/budgets", params={"period": period})

    assert response.status_code == 422


def test_service_converts_period_to_first_day_of_month(monkeypatch):
    from app.services import budgets as service

    captured = {}

    def fake_repository(db, user_id, *, period_start=None):
        captured["period_start"] = period_start
        return []

    monkeypatch.setattr(service.repository, "get_budgets_for_user", fake_repository)

    assert service.list_budgets(object(), uuid.uuid4(), period="2026-11") == []
    assert captured["period_start"] == date(2026, 11, 1)


def test_repository_filters_by_owner_and_period_start():
    from app.repositories import budgets as repository

    class RecordingSession:
        statement = None

        def scalars(self, statement):
            RecordingSession.statement = statement
            return SimpleNamespace(all=lambda: [])

    user_id = uuid.uuid4()
    repository.get_budgets_for_user(RecordingSession(), user_id, period_start=date(2026, 11, 1))

    sql = str(RecordingSession.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "budgets.user_id" in sql
    assert "budgets.period_start = '2026-11-01'" in sql
