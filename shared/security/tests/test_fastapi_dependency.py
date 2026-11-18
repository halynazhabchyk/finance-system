"""HTTP behaviour of the shared token dependency: 401 / 403 insufficient_scope / 200 (ЛР №5, 3.4, 4.2)."""

import logging
import uuid
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Security
from fastapi.testclient import TestClient

from shared.security.fastapi import bearer_token_dependency, get_token_verifier
from shared.security.jwt import VerifiedToken
from shared.security.openapi import authorization_code_scheme
from shared.security.testing import make_token, make_verifier

scheme = authorization_code_scheme(["budgets:read", "budgets:write"], auto_error=False)
verified_token = bearer_token_dependency(scheme)


def current_user(token: Annotated[VerifiedToken, Security(verified_token)]) -> uuid.UUID:
    return token.user_id


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/budgets", dependencies=[Security(current_user, scopes=["budgets:read"])])
    def read() -> dict:
        return {"ok": True}

    @app.post("/budgets")
    def write(user_id: Annotated[uuid.UUID, Security(current_user, scopes=["budgets:write"])]) -> dict:
        return {"user_id": str(user_id)}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.dependency_overrides[get_token_verifier] = lambda: make_verifier("budget-service")
    return TestClient(app)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_no_token_is_401_with_bearer_challenge(client):
    response = client.get("/budgets")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401_with_generic_message(client):
    response = client.get("/budgets", headers=bearer(make_token(issuer="http://evil.example")))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    assert response.json() == {"detail": "Invalid or missing access token."}  # no internal reason


def test_valid_token_with_scope_is_200(client):
    assert client.get("/budgets", headers=bearer(make_token(scopes=("budgets:read",)))).status_code == 200


def test_missing_scope_is_403_insufficient_scope(client):
    response = client.post("/budgets", headers=bearer(make_token(scopes=("budgets:read",))))

    assert response.status_code == 403
    assert response.headers["www-authenticate"] == 'Bearer error="insufficient_scope", scope="budgets:write"'


def test_user_id_comes_only_from_the_verified_token(client):
    sub = uuid.uuid4()
    response = client.post("/budgets", headers=bearer(make_token(sub, scopes=("budgets:read", "budgets:write"))))

    assert response.json() == {"user_id": str(sub)}


def test_public_endpoint_needs_no_token(client):
    assert client.get("/health").status_code == 200


def test_tokens_are_never_logged(client, caplog):
    token = make_token(scopes=("budgets:read",))
    with caplog.at_level(logging.INFO, logger="security.token"):
        client.get("/budgets", headers=bearer(token))
        client.post("/budgets", headers=bearer(token))
        client.get("/budgets", headers=bearer(make_token(algorithm="HS256")))

    text = caplog.text
    assert "token_verified" in text and "insufficient_scope" in text and "algorithm_not_allowed" in text
    assert token not in text
    assert token.split(".")[1] not in text  # not even the payload part
