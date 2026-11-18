"""Budget Service verifies the Keycloak token itself (ЛР №5, requirements 3.1–3.4, 7.2)."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
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
    api.user_service_error = HTTPException(status_code=403, detail="The user account is not allowed to use the service.")

    response = api.client.get("/internal/budgets", headers=bearer(make_token()))

    assert response.status_code == 403


def test_health_and_docs_are_public(api):
    assert api.client.get("/internal/health").status_code == 200
    assert api.client.get("/docs").status_code == 200
    assert api.client.get("/openapi.json").status_code == 200
