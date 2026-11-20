"""Traefik route declared by the service itself."""

from app.runtime import GATEWAY_TAGS


def test_agent_prefix_is_stripped_so_the_card_is_at_well_known_path():
    assert "traefik.http.routers.budget-agent.rule=PathPrefix(`/agents/budget`)" in GATEWAY_TAGS
    assert "traefik.http.middlewares.budget-agent-strip.stripprefix.prefixes=/agents/budget" in GATEWAY_TAGS
