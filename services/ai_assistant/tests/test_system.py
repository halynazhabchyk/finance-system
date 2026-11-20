"""The assistant starts as an ordinary HTTP service with a health check for Consul."""

from fastapi.testclient import TestClient


def test_health_endpoint_for_consul():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_are_assembled_from_environment():
    from app.core.config import get_settings

    settings = get_settings()

    assert settings.llm.model == "gemini-test"
    assert settings.gateway.base_url == "http://gateway.test"
    assert settings.limits.max_tool_iterations > 0
