"""Builders of Traefik route tags registered in Consul."""

from shared.service_discovery.consul import api_route_tags, gateway_route_tags


def test_api_route_maps_public_prefix_to_internal():
    tags = api_route_tags("budget-service", "/api/budgets", "/internal/budgets")

    assert "traefik.http.routers.budget-service.rule=PathPrefix(`/api/budgets`)" in tags
    assert "traefik.http.middlewares.budget-service-strip.stripprefix.prefixes=/api/budgets" in tags
    assert "traefik.http.middlewares.budget-service-internal.addprefix.prefix=/internal/budgets" in tags


def test_api_route_publishes_swagger_ui_and_openapi():
    tags = api_route_tags("budget-service", "/api/budgets", "/internal/budgets")

    assert "traefik.http.routers.budget-service-docs.rule=PathPrefix(`/api/budgets/docs`)" in tags
    assert "traefik.http.routers.budget-service-openapi.rule=Path(`/api/budgets/openapi.json`)" in tags
    assert "traefik.http.routers.budget-service-docs.priority=200" in tags


def test_api_route_rule_can_be_narrowed():
    tags = api_route_tags("user-service", "/api/users", "/internal/users", rule="PathRegexp(`^/api/users/x$`)")

    assert "traefik.http.routers.user-service.rule=PathRegexp(`^/api/users/x$`)" in tags
    assert "traefik.http.routers.user-service-docs.rule=PathPrefix(`/api/users/docs`)" in tags


def test_gateway_route_keeps_or_strips_the_prefix():
    kept = gateway_route_tags("mcp-server", "/mcp", strip_prefix=False)
    stripped = gateway_route_tags("budget-agent", "/agents/budget", strip_prefix=True)

    assert "traefik.http.routers.mcp-server.rule=PathPrefix(`/mcp`)" in kept
    assert not any("middlewares" in tag for tag in kept)
    assert "traefik.http.middlewares.budget-agent-strip.stripprefix.prefixes=/agents/budget" in stripped
