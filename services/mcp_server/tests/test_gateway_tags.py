"""Traefik route declared by the service itself."""

from app.main import GATEWAY_TAGS


def test_mcp_endpoint_keeps_its_path():
    assert "traefik.http.routers.mcp-server.rule=PathPrefix(`/mcp`)" in GATEWAY_TAGS
    assert not any("middlewares" in tag for tag in GATEWAY_TAGS)
