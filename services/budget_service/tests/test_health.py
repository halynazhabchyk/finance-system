"""Readiness: /internal/health reflects the availability of the service database."""

import pytest
from fastapi.testclient import TestClient

from app.api.routers import system
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_is_ok_when_database_answers(client, monkeypatch):
    monkeypatch.setattr(system, "database_available", lambda engine: True)

    response = client.get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(system, "database_available", lambda engine: False)

    response = client.get("/internal/health")

    assert response.status_code == 503
    assert "database is unavailable" in response.json()["detail"]
