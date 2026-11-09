import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["CONSUL_ENABLED"] = "false"

VALID_TOKEN = "valid-token"
EMAIL = "student@example.com"
PASSWORD = "secret-password"


@pytest.fixture
def received_texts() -> list[str]:
    """Texts that reached the test agent (to check what the client actually sent)."""
    return []


@pytest.fixture
def gateway(received_texts):
    """Traefik stand-in: login of User Service + a real A2A agent at /agents/budget."""
    import httpx
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    from a2a_chat.tests.fake_agent import create_text_agent

    async def login(request: Request) -> JSONResponse:
        form = await request.form()
        if form.get("username") == EMAIL and form.get("password") == PASSWORD:
            return JSONResponse({"access_token": VALID_TOKEN, "token_type": "bearer"})
        return JSONResponse({"detail": "Incorrect email or password"}, status_code=401)

    app = Starlette(
        routes=[
            Route("/api/users/auth/login", login, methods=["POST"]),
            Mount("/agents/budget", app=create_text_agent(received_texts, valid_token=VALID_TOKEN)),
        ]
    )
    return httpx.ASGITransport(app=app)


@pytest.fixture
def remote(gateway):
    from shared.ai_tools.a2a.client import RemoteAgentClient

    def connect(token: str = VALID_TOKEN) -> RemoteAgentClient:
        return RemoteAgentClient(base_url="http://gateway.test/agents/budget", access_token=token, transport=gateway)

    return connect


@pytest.fixture
def output() -> list[str]:
    return []


@pytest.fixture
def console(output):
    from a2a_chat.console import Console

    return Console(write=output.append)
