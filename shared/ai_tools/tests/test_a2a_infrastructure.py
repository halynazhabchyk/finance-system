"""Shared A2A infrastructure: JWT middleware (also under a path prefix), request parsing."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.testclient import TestClient

from shared.ai_tools.a2a.server.auth import BearerAuthMiddleware
from shared.ai_tools.a2a.requests import normalize_numbers
from shared.ai_tools.gateway.client import AccountBlocked, AuthenticationFailed


async def verifier(token: str) -> None:
    if token == "blocked":
        raise AccountBlocked("blocked")
    if token != "good":
        raise AuthenticationFailed("bad")


def _agent() -> Starlette:
    async def rpc(_):
        return PlainTextResponse("task created")

    async def card(_):
        return PlainTextResponse("card")

    app = Starlette(routes=[Route("/", rpc, methods=["POST"]), Route("/.well-known/agent-card.json", card)])
    app.add_middleware(BearerAuthMiddleware, verifier=verifier, protected_paths=("/",))
    return app


@pytest.fixture(params=["root", "mounted"])
def client(request):
    if request.param == "root":
        return TestClient(_agent()), ""
    return TestClient(Starlette(routes=[Mount("/agents/budget", app=_agent())])), "/agents/budget"


@pytest.mark.parametrize(
    "headers,status",
    [({}, 401), ({"Authorization": "Bearer bad"}, 401), ({"Authorization": "Basic good"}, 401), ({"Authorization": "Bearer blocked"}, 403), ({"Authorization": "Bearer good"}, 200)],
)
def test_rpc_endpoint_requires_valid_jwt(client, headers, status):
    http, prefix = client
    assert http.post(f"{prefix}/", headers=headers).status_code == status


def test_agent_card_stays_public(client):
    http, prefix = client
    assert http.get(f"{prefix}/.well-known/agent-card.json").text == "card"


def test_protobuf_numbers_are_normalized():
    assert normalize_numbers({"year": 2026.0, "amount": 250.5, "nested": [{"month": 11.0}]}) == {
        "year": 2026,
        "amount": 250.5,
        "nested": [{"month": 11}],
    }
