"""User Service API with Keycloak tokens (ЛР №5: 2.7 first sign-in, 3.3 ownership, 3.4 statuses)."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from shared.security.testing import make_token, make_verifier


def profile(user_id, *, is_active=True, email="vander@example.com", user_name="Vander Liin"):
    return SimpleNamespace(
        user_id=user_id,
        user_name=user_name,
        email=email,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        is_active=is_active,
    )


class FakeDb:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def refresh(self, item):
        pass


@pytest.fixture
def api(monkeypatch):
    """App with the test JWKS and an in-memory repository."""
    from app.api.dependencies import get_db
    from app.main import app
    from app.repositories import users as repository
    from shared.security.fastapi import get_token_verifier

    state = SimpleNamespace(users={}, db=FakeDb())

    def create(db, *, user_id, user_name, email):
        state.users[user_id] = profile(user_id, email=email, user_name=user_name)
        return state.users[user_id]

    monkeypatch.setattr(repository, "get_by_id", lambda db, user_id: state.users.get(user_id))
    monkeypatch.setattr(repository, "get_by_email", lambda db, email: next((u for u in state.users.values() if u.email == email), None))
    monkeypatch.setattr(repository, "create", create)
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier("user-service")
    app.dependency_overrides[get_db] = lambda: state.db
    state.client = TestClient(app)
    yield state
    app.dependency_overrides.clear()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_no_token_is_401(api):
    response = api.client.get(f"/internal/users/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_former_hs256_token_is_401(api):
    user_id = uuid.uuid4()

    assert api.client.get(f"/internal/users/{user_id}", headers=bearer(make_token(user_id, algorithm="HS256"))).status_code == 401


def test_first_request_creates_profile_from_token_claims(api):
    sub = uuid.uuid4()
    token = make_token(sub, email="Halyna@Example.com", name="Halyna Zh")

    response = api.client.get(f"/internal/users/{sub}", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["user_id"] == str(sub)  # user_id = sub
    assert response.json()["email"] == "halyna@example.com"
    assert response.json()["user_name"] == "Halyna Zh"
    assert list(api.users) == [sub]


def test_existing_profile_is_returned_without_duplicates(api):
    sub = uuid.uuid4()
    api.users[sub] = profile(sub)

    response = api.client.get(f"/internal/users/{sub}", headers=bearer(make_token(sub, email="vander@example.com")))

    assert response.status_code == 200
    assert response.json()["user_name"] == "Vander Liin"
    assert api.db.commits == 0


def test_another_users_profile_is_403(api):
    me, other = uuid.uuid4(), uuid.uuid4()
    api.users[other] = profile(other, email="other@example.com")

    response = api.client.get(f"/internal/users/{other}", headers=bearer(make_token(me)))

    assert response.status_code == 403


def test_blocked_profile_is_403(api):
    sub = uuid.uuid4()
    api.users[sub] = profile(sub, is_active=False)

    response = api.client.get(f"/internal/users/{sub}", headers=bearer(make_token(sub)))

    assert response.status_code == 403
    assert response.json() == {"detail": "The user account is blocked."}


def test_renaming_another_user_is_403(api, monkeypatch):
    me, other = uuid.uuid4(), uuid.uuid4()

    response = api.client.patch(f"/internal/users/{other}/name", json={"user_name": "Hacker"}, headers=bearer(make_token(me)))

    assert response.status_code == 403


def test_password_registration_and_login_are_removed(api):
    """ЛР №5 (Р7): accounts are registered in Keycloak; User Service keeps no passwords."""
    registration = api.client.post(
        "/internal/users",
        json={"user_name": "Lab", "email": "lab@example.com", "password": "password123"},
    )
    login = api.client.post("/internal/auth/login", data={"username": "lab@example.com", "password": "password123"})

    assert registration.status_code == 405
    assert login.status_code == 404
