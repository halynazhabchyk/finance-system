"""Budget Service verifies the Keycloak token itself."""

import uuid
from types import SimpleNamespace

import pytest
from shared.errors import PermissionDeniedError
from fastapi.testclient import TestClient

from shared.security.testing import make_token, make_verifier


@pytest.fixture
def api(monkeypatch):
    """App with the test JWKS and a recorded User Service (Open Host Service) call."""
    import app.api.dependencies as dependencies
    from app.api.dependencies import get_db
    from app.main import app
    from shared.security.fastapi import get_token_verifier

    calls = []
    state = SimpleNamespace(calls=calls, user_service_error=None)

    def fake_validate(token, user_id):
        calls.append((token, user_id))
        if state.user_service_error:
            raise state.user_service_error
        return {"user_id": str(user_id), "is_active": True}

    monkeypatch.setattr(dependencies, "validate_user_token", fake_validate)
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier("budget-service")
    app.dependency_overrides[get_db] = lambda: iter([object()])
    state.client = TestClient(app)
    yield state
    app.dependency_overrides.clear()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_token_is_401(api):
    response = api.client.get(f"/internal/budgets/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert api.calls == []


@pytest.mark.parametrize(
    "token",
    [
        make_token(algorithm="HS256"),  # the former User Service token
        make_token(audience=("report-service",)),  # token for another service
        make_token(expires_in=-3600),
        "broken",
    ],
    ids=["hs256", "foreign-audience", "expired", "garbage"],
)
def test_untrusted_token_is_401_before_user_service_is_called(api, token):
    response = api.client.get(f"/internal/budgets/{uuid.uuid4()}", headers=bearer(token))

    assert response.status_code == 401
    assert api.calls == []


def test_valid_token_is_forwarded_unchanged_and_user_id_is_sub(api, monkeypatch):
    from app.api.routers import budgets as router_module

    sub = uuid.uuid4()
    token = make_token(sub)
    seen = {}

    def list_budgets(db, user_id, period=None):
        seen["user"] = user_id
        return []

    monkeypatch.setattr(router_module.budget_service, "list_budgets", list_budgets)

    response = api.client.get("/internal/budgets", headers=bearer(token))

    assert response.status_code == 200
    assert api.calls == [(token, sub)]
    assert seen["user"] == sub


def test_another_users_budget_is_404(api, monkeypatch):
    from app.repositories import budgets as repository

    owner, intruder = uuid.uuid4(), uuid.uuid4()
    budget_id = uuid.uuid4()
    monkeypatch.setattr(repository, "get_budget", lambda db, requested_id, for_update=False: SimpleNamespace(budget_id=budget_id, user_id=owner))

    response = api.client.get(f"/internal/budgets/{budget_id}", headers=bearer(make_token(intruder)))

    assert response.status_code == 404
    assert response.json() == {"detail": "Budget was not found."}


def test_blocked_account_reported_by_user_service_is_403(api):
    api.user_service_error = PermissionDeniedError("The user account is not allowed to use the service.")

    response = api.client.get("/internal/budgets", headers=bearer(make_token()))

    assert response.status_code == 403


def test_health_and_docs_are_public(api):
    assert api.client.get("/internal/health").status_code == 200
    assert api.client.get("/docs").status_code == 200
    assert api.client.get("/openapi.json").status_code == 200


# --- scopes ---

READ_ONLY = ("users:read", "budgets:read")


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/internal/budgets"),
        ("patch", "/internal/budgets/{id}"),
        ("delete", "/internal/budgets/{id}"),
        ("post", "/internal/budgets/{id}/categories"),
        ("patch", "/internal/budgets/{id}/categories/{id}"),
        ("delete", "/internal/budgets/{id}/categories/{id}"),
        ("post", "/internal/budgets/{id}/expenses"),
        ("patch", "/internal/budgets/{id}/expenses/{id}"),
        ("delete", "/internal/budgets/{id}/expenses/{id}"),
    ],
)
def test_changes_without_budgets_write_are_403_insufficient_scope(api, method, path):
    url = path.replace("{id}", str(uuid.uuid4()))

    response = api.client.request(method.upper(), url, headers=bearer(make_token(scopes=READ_ONLY)), json={})

    assert response.status_code == 403
    assert response.headers["www-authenticate"] == 'Bearer error="insufficient_scope", scope="budgets:write"'
    assert api.calls == []  # rejected locally, User Service is not asked


@pytest.mark.parametrize(
    "path",
    ["/internal/budgets", "/internal/budgets/{id}", "/internal/budgets/{id}/expenses", "/internal/budgets/{id}/expenses/{id}/saga"],
)
def test_reading_without_budgets_read_is_403(api, path):
    url = path.replace("{id}", str(uuid.uuid4()))

    response = api.client.get(url, headers=bearer(make_token(scopes=("users:read", "budgets:write"))))

    assert response.status_code == 403
    assert 'scope="budgets:read"' in response.headers["www-authenticate"]


def test_create_budget_with_budgets_write_is_201(api, monkeypatch):
    from datetime import datetime, timezone

    from app.api.routers import budgets as router_module

    sub = uuid.uuid4()

    def create_budget(db, user_id, payload):
        return SimpleNamespace(
            budget_id=uuid.uuid4(), user_id=user_id, period_start=payload.period_start, period_end=payload.period_end,
            total_amount=payload.total_amount, currency=payload.currency, created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(router_module.budget_service, "create_budget", create_budget)
    token = make_token(sub, scopes=("users:read", "budgets:read", "budgets:write"))

    response = api.client.post("/internal/budgets", headers=bearer(token), json={"period_start": "2026-11-01", "period_end": "2026-11-30", "total_amount": "1000.00"})

    assert response.status_code == 201, response.text
    assert api.calls == [(token, sub)]
