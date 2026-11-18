"""Shared CORS policy (ЛР №5, requirement 1)."""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from shared.security.cors import (
    CorsConfigurationError,
    CorsSettings,
    install_cors,
    parse_allowed_origins,
)

ALLOWED = "https://cad.kpi.ua"


def build_client(origins: tuple[str, ...] = (ALLOWED, "http://cad.kpi.ua")) -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    def protected() -> dict:
        # Stands in for an endpoint that requires a token: the preflight must not reach it.
        raise HTTPException(status_code=401, detail="Bearer access token is required.", headers={"WWW-Authenticate": "Bearer"})

    install_cors(app, CorsSettings(allowed_origins=origins))
    return TestClient(app)


def preflight(client: TestClient, origin: str, method: str = "GET", headers: str = "authorization"):
    return client.options(
        "/protected",
        headers={"Origin": origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": headers},
    )


def test_preflight_from_department_site_is_allowed():
    response = preflight(build_client(), ALLOWED)

    assert response.status_code == 200
    assert response.headers.get_list("access-control-allow-origin") == [ALLOWED]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in response.headers


def test_preflight_from_unknown_origin_gets_no_allowing_headers():
    response = preflight(build_client(), "https://example.com")

    assert response.status_code == 400
    assert not [name for name in response.headers if name.lower().startswith("access-control-")]


def test_preflight_is_not_blocked_by_authentication():
    """OPTIONS is answered by the middleware; the endpoint (here: always 401) is not executed."""
    assert preflight(build_client(), ALLOWED).status_code == 200


def test_disallowed_header_or_method_is_rejected():
    client = build_client()

    assert preflight(client, ALLOWED, headers="x-custom-header").status_code == 400
    assert preflight(client, ALLOWED, method="TRACE").status_code == 400


def test_error_responses_carry_cors_header_so_browser_sees_real_status():
    response = build_client().get("/protected", headers={"Origin": ALLOWED})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_actual_request_from_unknown_origin_has_no_allow_origin():
    response = build_client().get("/protected", headers={"Origin": "https://example.com"})

    assert "access-control-allow-origin" not in response.headers


def test_parse_normalizes_and_deduplicates():
    raw = " https://cad.kpi.ua/ , http://cad.kpi.ua,https://cad.kpi.ua,, http://localhost:8080 "

    assert parse_allowed_origins(raw) == ("https://cad.kpi.ua", "http://cad.kpi.ua", "http://localhost:8080")


@pytest.mark.parametrize("raw", ["*", "https://*.kpi.ua", "cad.kpi.ua", "https://cad.kpi.ua/path", "ftp://cad.kpi.ua"])
def test_parse_rejects_wildcards_and_non_origins(raw):
    with pytest.raises(CorsConfigurationError):
        parse_allowed_origins(raw)


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://cad.kpi.ua,http://localhost:8080")

    assert CorsSettings.from_env().allowed_origins == ("https://cad.kpi.ua", "http://localhost:8080")


def test_empty_configuration_allows_no_origin(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    client = build_client(CorsSettings.from_env().allowed_origins)

    assert "access-control-allow-origin" not in preflight(client, ALLOWED).headers
