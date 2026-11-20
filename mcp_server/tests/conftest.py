import os

import pytest


os.environ["CONSUL_ENABLED"] = "false"
os.environ["MCP_TRANSPORT"] = "stdio"


@pytest.fixture
def api():
    from ai_tools.testing import FakeFinanceApi

    return FakeFinanceApi()


@pytest.fixture
def mcp_server(api):
    """The MCP server wired to the in-memory API; the API client records every request."""
    from app.core.config import McpSettings
    from app.core.context import McpDependencies
    from app.server import build_server
    from ai_tools.gateway import FinanceApiClient

    deps = McpDependencies(
        McpSettings.from_env(),
        lambda token: FinanceApiClient(base_url="http://gateway.test", access_token=token, transport=api.transport()),
    )
    return build_server(deps)


@pytest.fixture
def stdio_user(api, monkeypatch):
    """stdio mode: the JWT of the local user comes from MCP_USER_JWT."""
    monkeypatch.setenv("MCP_USER_JWT", api.token)
    return api
