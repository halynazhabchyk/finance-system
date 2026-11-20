"""User Service client: responses of the Open Host Service become domain errors."""

import uuid

import httpx
import pytest

from shared.clients import user_service as client
from shared.errors import AuthenticationError, ConflictError, PermissionDeniedError, ServiceUnavailableError
from shared.service_discovery.consul import ConsulError

USER_ID = uuid.uuid4()


@pytest.fixture
def respond(monkeypatch):
    """Discovery returns a fixed address; the HTTP reply is chosen by the test."""
    monkeypatch.setattr(client, "discover_service", lambda name, request_timeout: "http://user-service:8001")

    def set_reply(status_code: int, body: dict | None = None):
        def fake_get(url, headers, timeout):
            assert url == f"http://user-service:8001/internal/users/{USER_ID}"
            assert headers == {"Authorization": "Bearer token"}
            return httpx.Response(status_code, json=body or {})

        monkeypatch.setattr(client.httpx, "get", fake_get)

    return set_reply


def test_active_user_is_returned(respond):
    respond(200, {"user_id": str(USER_ID), "is_active": True})

    assert client.validate_user_token("token", USER_ID)["is_active"] is True


@pytest.mark.parametrize(
    "status_code,error",
    [
        (403, PermissionDeniedError),
        (409, ConflictError),
        (500, ServiceUnavailableError),
        (503, ServiceUnavailableError),
        (401, AuthenticationError),
        (404, AuthenticationError),
        (422, AuthenticationError),
    ],
)
def test_rejections_become_domain_errors(respond, status_code, error):
    respond(status_code)

    with pytest.raises(error):
        client.validate_user_token("token", USER_ID)


def test_unreachable_user_service_is_unavailable(monkeypatch):
    def refuse(name, request_timeout):
        raise ConsulError("no healthy instance")

    monkeypatch.setattr(client, "discover_service", refuse)

    with pytest.raises(ServiceUnavailableError):
        client.validate_user_token("token", USER_ID)
