"""Gateway routes of the AI components registered through Consul tags (requirements 2.6, 4.6, 5.7)."""

from shared.service_discovery.consul import default_traefik_tags


def test_assistant_uses_the_api_to_internal_mapping():
    tags = default_traefik_tags("ai-assistant")
    assert "traefik.http.routers.ai-assistant.rule=PathPrefix(`/api/assistant`)" in tags
    assert "traefik.http.middlewares.ai-assistant-internal.addprefix.prefix=/internal/assistant" in tags
    assert "traefik.http.routers.ai-assistant-docs.rule=PathPrefix(`/api/assistant/docs`)" in tags


def test_mcp_endpoint_keeps_its_path():
    tags = default_traefik_tags("mcp-server")
    assert "traefik.http.routers.mcp-server.rule=PathPrefix(`/mcp`)" in tags
    assert not any("middlewares" in tag for tag in tags)


def test_agents_prefix_is_stripped_so_the_card_is_at_well_known_path():
    for name, prefix in (("budget-agent", "/agents/budget"), ("report-agent", "/agents/report")):
        tags = default_traefik_tags(name)
        assert f"traefik.http.routers.{name}.rule=PathPrefix(`{prefix}`)" in tags
        assert f"traefik.http.middlewares.{name}-strip.stripprefix.prefixes={prefix}" in tags


def test_existing_business_routes_are_unchanged():
    tags = default_traefik_tags("budget-service")
    assert "traefik.http.routers.budget-service.rule=PathPrefix(`/api/budgets`)" in tags
    assert "traefik.http.middlewares.budget-service-internal.addprefix.prefix=/internal/budgets" in tags
    assert default_traefik_tags("scheduler") == []
