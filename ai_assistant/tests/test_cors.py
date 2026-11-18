"""CORS of the service through the shared module (ЛР №5, requirement 1)."""

from fastapi.testclient import TestClient

PROTECTED_PATH = "/internal/assistant/chat"


def make_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://cad.kpi.ua,http://cad.kpi.ua")
    from app.runtime import create_app

    return TestClient(create_app())


def preflight(client: TestClient, origin: str):
    return client.options(
        PROTECTED_PATH,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_preflight_from_department_site_is_allowed_without_token(monkeypatch):
    response = preflight(make_client(monkeypatch), "https://cad.kpi.ua")

    assert response.status_code == 200
    assert response.headers.get_list("access-control-allow-origin") == ["https://cad.kpi.ua"]
    assert "access-control-allow-credentials" not in response.headers


def test_preflight_from_unknown_origin_is_rejected(monkeypatch):
    response = preflight(make_client(monkeypatch), "https://example.com")

    assert response.status_code == 400
    assert not [name for name in response.headers if name.lower().startswith("access-control-")]
