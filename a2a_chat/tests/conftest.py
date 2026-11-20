import os

import pytest


os.environ["CONSUL_ENABLED"] = "false"

from shared.security.testing import make_token  # noqa: E402

VALID_TOKEN = make_token(preferred_username="student")


@pytest.fixture
def received_texts() -> list[str]:
    """Texts that reached the test agent (to check what the client actually sent)."""
    return []


@pytest.fixture
def gateway(received_texts):
    """Traefik stand-in: a real A2A agent at /agents/budget."""
    import httpx
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from a2a_chat.tests.fake_agent import create_text_agent

    app = Starlette(
        routes=[
            Mount("/agents/budget", app=create_text_agent(received_texts, valid_token=VALID_TOKEN)),
        ]
    )
    return httpx.ASGITransport(app=app)


@pytest.fixture
def remote(gateway):
    from ai_tools.a2a.client import RemoteAgentClient

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
