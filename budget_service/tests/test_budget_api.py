import uuid
from types import SimpleNamespace


def test_budget_endpoint_requires_authentication(client):
    response = client.get("/internal/budgets")

    assert response.status_code == 401


def test_create_budget_returns_contract(client, monkeypatch):
    from app.api.routers import budgets as router_module

    user_id = uuid.uuid4()
    budget_id = uuid.uuid4()
    budget = SimpleNamespace(
        budget_id=budget_id,
        user_id=user_id,
        period_start="2026-01-01",
        period_end="2026-01-31",
        total_amount="1000.00",
        currency="UAH",
        created_at="2026-01-01T00:00:00Z",
    )
    monkeypatch.setattr(router_module.budgets, "create_budget", lambda db, uid, payload: budget)
    from app.api.dependencies import get_current_user, get_db
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_id
    app.dependency_overrides[get_db] = lambda: iter([object()])
    try:
        response = client.post(
            "/internal/budgets",
            json={
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "total_amount": "1000.00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["currency"] == "UAH"
    assert response.json()["total_amount"] == "1000.00"


def test_budget_rejects_non_calendar_month(client):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: uuid.uuid4()
    try:
        response = client.post(
            "/internal/budgets",
            json={
                "period_start": "2026-01-02",
                "period_end": "2026-01-31",
                "total_amount": "1000.00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
