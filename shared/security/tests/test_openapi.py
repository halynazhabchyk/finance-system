"""Swagger UI login through Keycloak."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared.security.openapi import authorization_code_scheme, swagger_ui_oauth_config

ISSUER = "http://localhost:8080/auth/realms/finance"


def build_app(scopes):
    scheme = authorization_code_scheme(scopes)
    app = FastAPI(swagger_ui_init_oauth=swagger_ui_oauth_config(scopes))

    @app.get("/protected")
    def protected(token: str = Depends(scheme)) -> dict:
        return {"length": len(token)}

    return app


def test_openapi_documents_authorization_code_flow_with_service_scopes(monkeypatch):
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    schema = TestClient(build_app(["budgets:read", "budgets:write"])).get("/openapi.json").json()

    flows = schema["components"]["securitySchemes"]["OAuth2AuthorizationCodeBearer"]["flows"]
    assert list(flows) == ["authorizationCode"]  # no password flow any more
    assert flows["authorizationCode"]["authorizationUrl"] == f"{ISSUER}/protocol/openid-connect/auth"
    assert flows["authorizationCode"]["tokenUrl"] == f"{ISSUER}/protocol/openid-connect/token"
    assert set(flows["authorizationCode"]["scopes"]) == {"budgets:read", "budgets:write"}


def test_swagger_ui_uses_pkce_public_client_and_preselects_only_read_scopes():
    config = swagger_ui_oauth_config(["budgets:read", "budgets:write"])

    assert config == {"clientId": "finance-swagger", "usePkceWithAuthorizationCodeGrant": True, "scopes": "budgets:read"}


def test_swagger_page_contains_pkce_setting():
    html = TestClient(build_app(["reports:read"])).get("/docs").text

    assert "usePkceWithAuthorizationCodeGrant" in html
    assert "finance-swagger" in html


def test_bearer_token_is_still_read_from_authorization_header():
    client = TestClient(build_app(["reports:read"]))

    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"Authorization": "Bearer abc"}).json() == {"length": 3}


def test_unknown_scope_is_a_programming_error():
    with pytest.raises(ValueError):
        authorization_code_scheme(["budgets:delete"])
