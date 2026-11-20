"""Traefik route declared by the service itself."""

from app.runtime import GATEWAY_TAGS


def test_report_route_maps_api_to_internal():
    assert "traefik.http.routers.report-service.rule=PathPrefix(`/api/reports`)" in GATEWAY_TAGS
    assert "traefik.http.middlewares.report-service-internal.addprefix.prefix=/internal/reports" in GATEWAY_TAGS
