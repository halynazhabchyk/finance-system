"""User Service publishes only the user's own profile through Traefik."""

import re

from app.runtime import GATEWAY_TAGS


def test_only_own_profile_routes_are_public():
    rule = next(tag for tag in GATEWAY_TAGS if tag.startswith("traefik.http.routers.user-service.rule="))
    pattern = re.search(r"PathRegexp\(`(.+)`\)", rule).group(1)
    profile = "/api/users/05d32d26-2657-4042-aa14-088b89b43bee"

    assert re.match(pattern, profile) and re.match(pattern, f"{profile}/name")
    for internal in ("/api/users", "/api/users/", f"{profile}/block", f"{profile}/activate", "/api/users/auth/login"):
        assert not re.match(pattern, internal), internal
    assert "traefik.http.routers.user-service-docs.rule=PathPrefix(`/api/users/docs`)" in GATEWAY_TAGS
