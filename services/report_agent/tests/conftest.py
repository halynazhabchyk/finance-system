import os

import pytest


os.environ["CONSUL_ENABLED"] = "false"
os.environ["GATEWAY_URL"] = "http://gateway.test"
os.environ["A2A_PUBLIC_URL"] = "http://localhost:8080/agents/report"
os.environ.pop("BUDGET_AGENT_URL", None)
os.environ.pop("LLM_API_KEY", None)


@pytest.fixture
def api():
    from ai_tools.testing import FakeFinanceApi

    return FakeFinanceApi()


@pytest.fixture
def gateway(api):
    """Traefik stand-in: /agents/budget/* -> the test budget-agent (A2A over ASGI)."""
    import httpx
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from tests.fake_budget_agent import create_fake_budget_agent

    budget_agent = create_fake_budget_agent(api)
    return httpx.ASGITransport(app=Starlette(routes=[Mount("/agents/budget", app=budget_agent)]))


@pytest.fixture
def remote(api, gateway):
    """A2A client of report-agent."""
    import httpx

    from ai_tools.a2a.client import RemoteAgentClient

    from app.runtime import create_app

    def connect(llm=None):
        app = create_app(api_transport=api.transport(), budget_agent_transport=gateway, llm=llm)
        return RemoteAgentClient(
            base_url="http://report-agent.test", access_token=api.token, transport=httpx.ASGITransport(app=app)
        )

    return connect
