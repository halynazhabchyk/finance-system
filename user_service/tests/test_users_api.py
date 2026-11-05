import uuid
from types import SimpleNamespace


def test_get_missing_user_returns_404(client, monkeypatch):
    from app.repositories import users as repository
    from app.core.security import create_access_token

    user_id = uuid.uuid4()
    monkeypatch.setattr(repository, "get_by_id", lambda db, user_id: None)

    response = client.get(
        f"/internal/users/{user_id}",
        headers={"Authorization": f"Bearer {create_access_token(str(user_id))}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User was not found."


def test_create_user_rejects_invalid_payload(client):
    response = client.post(
        "/internal/users",
        json={"user_name": "A", "email": "invalid", "password": "short"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_user_response_keeps_name_and_email_separate(client, monkeypatch):
    from app.repositories import users as repository
    from app.core.security import create_access_token

    user_id = uuid.uuid4()
    user = SimpleNamespace(
        user_id=user_id,
        user_name="Vander Liin",
        email="vander@example.com",
        created_at="2026-01-01T00:00:00Z",
        is_active=True,
    )
    monkeypatch.setattr(repository, "get_by_id", lambda db, requested_id: user)

    response = client.get(
        f"/internal/users/{user_id}",
        headers={"Authorization": f"Bearer {create_access_token(str(user_id))}"},
    )

    assert response.status_code == 200
    assert response.json()["user_name"] == "Vander Liin"
    assert response.json()["email"] == "vander@example.com"
