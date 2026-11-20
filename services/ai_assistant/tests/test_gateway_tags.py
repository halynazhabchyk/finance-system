"""Traefik route declared by the service itself."""

from app.runtime import GATEWAY_TAGS


def test_assistant_route_maps_api_to_internal():
    assert "traefik.http.routers.ai-assistant.rule=PathPrefix(`/api/assistant`)" in GATEWAY_TAGS
    assert "traefik.http.middlewares.ai-assistant-internal.addprefix.prefix=/internal/assistant" in GATEWAY_TAGS
