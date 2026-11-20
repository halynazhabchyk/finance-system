"""Traefik route declared by the service itself."""

from app.runtime import GATEWAY_TAGS


def test_budget_route_maps_api_to_internal():
    assert "traefik.http.routers.budget-service.rule=PathPrefix(`/api/budgets`)" in GATEWAY_TAGS
    assert "traefik.http.middlewares.budget-service-internal.addprefix.prefix=/internal/budgets" in GATEWAY_TAGS
