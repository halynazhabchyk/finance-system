import os
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["CONSUL_ENABLED"] = "false"
os.environ["GATEWAY_URL"] = "http://gateway.test"
os.environ["A2A_PUBLIC_URL"] = "http://localhost:8080/agents/budget"
os.environ["A2A_SAGA_WAIT_SECONDS"] = "5"
os.environ.pop("LLM_API_KEY", None)

AGENT_URL = "http://budget-agent.test"


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
def api():
    from shared.ai_tools.testing import FakeFinanceApi

    return FakeFinanceApi()


@pytest.fixture
def agent_app(api):
    from app.runtime import create_app

    def build(llm=None):
        return create_app(api_transport=api.transport(), llm=llm, sleep=no_sleep)

    return build


@pytest.fixture
def remote(agent_app, api):
    """A2A client of budget-agent (the same client report-agent uses), over ASGI – no network."""
    import httpx

    from shared.ai_tools.a2a.client import RemoteAgentClient

    def connect(token=None, llm=None):
        return RemoteAgentClient(
            base_url=AGENT_URL,
            access_token=token or api.token,
            transport=httpx.ASGITransport(app=agent_app(llm)),
        )

    return connect
