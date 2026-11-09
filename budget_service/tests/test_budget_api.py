import uuid
from types import SimpleNamespace


def test_budget_endpoint_requires_authentication(client):
    response = client.get("/internal/budgets")

    assert response.status_code == 401


def test_create_budget_returns_contract(client, as_user, monkeypatch):
    from app.api.routers import budgets as router_module

    user_id = uuid.uuid4()
    budget = SimpleNamespace(
        budget_id=uuid.uuid4(),
        user_id=user_id,
        period_start="2026-01-01",
        period_end="2026-01-31",
        total_amount="1000.00",
        currency="UAH",
        created_at="2026-01-01T00:00:00Z",
    )
    monkeypatch.setattr(router_module.budget_service, "create_budget", lambda db, uid, payload: budget)
    as_user(user_id)

    response = client.post(
        "/internal/budgets",
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "total_amount": "1000.00"},
    )

    assert response.status_code == 201
    assert response.json()["currency"] == "UAH"
    assert response.json()["total_amount"] == "1000.00"


def test_budget_rejects_non_calendar_month(client, as_user):
    as_user(uuid.uuid4())

    response = client.post(
        "/internal/budgets",
        json={"period_start": "2026-01-02", "period_end": "2026-01-31", "total_amount": "1000.00"},
    )

    assert response.status_code == 422


def test_domain_errors_keep_http_status_and_detail(client, as_user, monkeypatch):
    """Services raise domain errors; the API maps them to the same statuses as before."""
    from app.api.routers import budgets as router_module
    from shared.errors import NotFoundError

    def missing(db, budget_id, user_id):
        raise NotFoundError("Budget was not found.")

    monkeypatch.setattr(router_module.budget_service, "get_budget_summary", missing)
    as_user(uuid.uuid4())

    response = client.get(f"/internal/budgets/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Budget was not found."}
