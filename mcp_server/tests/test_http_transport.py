"""Streamable HTTP transport (requirement 4.6): JWT from the header, health check, DNS-rebinding protection."""

import pytest
from starlette.testclient import TestClient

PROTOCOL = "2025-06-18"
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": PROTOCOL,
}
CALL = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {"name": "find_budget_by_period", "arguments": {"year": 2026, "month": 11}},
}


@pytest.fixture
def http(mcp_server, monkeypatch):
    from app.core.config import McpSettings
    from app.http_app import create_http_app

    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    app = create_http_app(mcp_server, McpSettings.from_env())
    with TestClient(app, base_url="http://localhost:8080") as client:
        yield client


def test_health_check_for_consul(http):
    assert http.get("/internal/health").json() == {"status": "ok"}


def test_initialize_over_http(http):
    response = http.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["serverInfo"]["name"] == "finance-mcp-server"
    assert "cannot change or delete" in result["instructions"]


def test_tool_call_uses_jwt_from_authorization_header(http, api):
    api.add_budget("2026-11")

    response = http.post("/mcp", json=CALL, headers={**HEADERS, "Authorization": f"Bearer {api.token}"})

    result = response.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["untrusted_data"]["found"] is True
    assert api.requests[-1].headers["Authorization"] == f"Bearer {api.token}"


def test_http_request_without_jwt_ignores_the_stdio_token(http, api, monkeypatch):
    # Even if MCP_USER_JWT is set in the container, a shared HTTP server must not act as that user.
    monkeypatch.setenv("MCP_USER_JWT", api.token)

    response = http.post("/mcp", json=CALL, headers=HEADERS)

    result = response.json()["result"]
    assert result["isError"] is True
    assert "Authentication required" in result["content"][0]["text"]
    assert api.requests == []


def test_foreign_host_header_is_rejected(http, api):
    response = http.post(
        "/mcp", json=CALL, headers={**HEADERS, "Host": "evil.example", "Authorization": f"Bearer {api.token}"}
    )
    assert response.status_code == 421
    assert api.requests == []
