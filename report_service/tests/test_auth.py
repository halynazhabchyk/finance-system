"""Report Service verifies the Keycloak token itself (ЛР №5, requirements 3.1–3.4, 7.2)."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from shared.security.testing import make_token, make_verifier


@pytest.fixture
def api(monkeypatch):
    import app.api.dependencies as dependencies
    from app.api.dependencies import get_db
    from app.main import app
    from shared.security.fastapi import get_token_verifier

    state = SimpleNamespace(calls=[], user_service_error=None)

    def fake_validate(token, user_id):
        state.calls.append((token, user_id))
        if state.user_service_error:
            raise state.user_service_error
        return {"user_id": str(user_id), "is_active": True}

    monkeypatch.setattr(dependencies, "validate_user_token", fake_validate)
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier("report-service")
    app.dependency_overrides[get_db] = lambda: iter([object()])
    state.client = TestClient(app)
    yield state
    app.dependency_overrides.clear()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_token_is_401(api):
    response = api.client.get("/internal/reports/monthly/2026/11")

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.parametrize(
    "token",
    [make_token(algorithm="HS256"), make_token(audience=("budget-service",)), make_token(issuer="http://evil.example")],
    ids=["hs256", "foreign-audience", "foreign-issuer"],
)
def test_untrusted_token_is_401(api, token):
    assert api.client.get("/internal/reports/annual/2026", headers=bearer(token)).status_code == 401
    assert api.calls == []


def test_report_is_built_for_the_token_subject_only(api, monkeypatch):
    from app.api.routers import reports as router_module

    sub = uuid.uuid4()
    token = make_token(sub)
    seen = {}

    def monthly(db, user_id, year, month):
        from shared.errors import NotFoundError

        seen["user"] = user_id
        raise NotFoundError("Report was not found.")

    monkeypatch.setattr(router_module.report_service, "get_monthly_report", monthly)
    response = api.client.get("/internal/reports/monthly/2026/11", headers=bearer(token))

    assert response.status_code == 404

    assert api.calls == [(token, sub)]  # the same token goes to User Service unchanged
    assert seen["user"] == sub  # reports are read for the verified subject, never for a client-supplied id


def test_blocked_account_is_403(api):
    api.user_service_error = HTTPException(status_code=403, detail="The user account is not allowed to use the service.")

    assert api.client.get("/internal/reports/annual/2026", headers=bearer(make_token())).status_code == 403


# --- ЛР №5, п. 4: OAuth scopes ----------------------------------------------------------------


@pytest.mark.parametrize("path", ["/internal/reports/monthly/2026/11", "/internal/reports/annual/2026"])
def test_reports_without_reports_read_are_403_insufficient_scope(api, path):
    response = api.client.get(path, headers=bearer(make_token(scopes=("users:read", "budgets:read"))))

    assert response.status_code == 403
    assert response.headers["www-authenticate"] == 'Bearer error="insufficient_scope", scope="reports:read"'
    assert api.calls == []
