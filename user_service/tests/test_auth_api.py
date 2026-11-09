from types import SimpleNamespace

import bcrypt
import jwt


def test_login_accepts_oauth2_form_and_returns_jwt(client, monkeypatch):
    from app.core.security import _jwt_secret
    from app.repositories import users as repository

    user = SimpleNamespace(
        user_id="1d7f0e2d-2f62-4b17-a5de-64e93d5238e4",
        password_hash=bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode(),
        is_active=True,
    )
    monkeypatch.setattr(repository, "get_by_email", lambda db, email: user)

    response = client.post(
        "/internal/auth/login",
        data={"username": "User@Example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert jwt.decode(body["access_token"], _jwt_secret(), algorithms=["HS256"])["sub"] == str(user.user_id)


def test_login_rejects_invalid_credentials(client, monkeypatch):
    from app.repositories import users as repository

    monkeypatch.setattr(repository, "get_by_email", lambda db, email: None)

    response = client.post(
        "/internal/auth/login",
        data={"username": "missing@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_rejects_invalid_form(client, monkeypatch):
    from app.repositories import users as repository

    monkeypatch.setattr(repository, "get_by_email", lambda db, email: None)

    response = client.post(
        "/internal/auth/login",
        data={"username": "not-an-email", "password": "password"},
    )

    assert response.status_code == 401


def test_invalid_credentials_keep_bearer_challenge_header(client, monkeypatch):
    from app.repositories import users as repository

    monkeypatch.setattr(repository, "get_by_email", lambda db, email: None)

    response = client.post(
        "/internal/auth/login",
        data={"username": "missing@example.com", "password": "wrong-password"},
    )

    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_blocked_user_cannot_log_in(client, monkeypatch):
    from types import SimpleNamespace

    from app.repositories import users as repository

    user = SimpleNamespace(user_id="u1", password_hash="hash", is_active=False)
    monkeypatch.setattr(repository, "get_by_email", lambda db, email: user)
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda password, hashed: True)

    response = client.post(
        "/internal/auth/login",
        data={"username": "blocked@example.com", "password": "secret-password"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "The user account is inactive."}
