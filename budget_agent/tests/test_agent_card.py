"""Agent Card of budget-agent (requirements 5.2, 5.3) and JWT protection of the A2A endpoint."""

import httpx
import pytest
from starlette.testclient import TestClient

from shared.ai_tools.testing import make_jwt

CARD_PATH = "/.well-known/agent-card.json"


@pytest.fixture
def http(agent_app):
    with TestClient(agent_app(), base_url="http://budget-agent.test") as client:
        yield client


def test_agent_card_is_public_and_describes_the_agent(http):
    card = http.get(CARD_PATH).json()

    assert card["name"] == "budget-agent"
    assert card["version"] == "1.0.0"
    assert card["supportedInterfaces"][0]["url"] == "http://localhost:8080/agents/budget/"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"
    assert card["supportedInterfaces"][0]["protocolVersion"] == "1.0"
    assert card["capabilities"]["streaming"] is True
    assert set(card["defaultInputModes"]) == {"application/json", "text/plain"}
    assert card["securitySchemes"]["bearerAuth"]["httpAuthSecurityScheme"] == {
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Access token of User Service (POST /api/users/auth/login).",
    }


def test_agent_card_declares_the_three_producer_skills(http):
    skills = {skill["id"]: skill for skill in http.get(CARD_PATH).json()["skills"]}

    assert set(skills) == {"register_expense", "manage_budget", "cancel_or_update_expense"}
    assert "ExpenseCreated" in skills["register_expense"]["tags"]
    assert {"BudgetCreated", "BudgetUpdated"} <= set(skills["manage_budget"]["tags"])
    assert {"ExpenseUpdated", "ExpenseDeleted"} <= set(skills["cancel_or_update_expense"]["tags"])
    for skill in skills.values():
        assert skill["name"] and skill["description"] and skill["examples"]


def test_health_check(http):
    assert http.get("/internal/health").json() == {"status": "ok"}


RPC = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {}}


def test_rpc_without_jwt_is_401(http):
    response = http.post("/", json=RPC)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_rpc_with_foreign_or_broken_jwt_is_401(http, api):
    import uuid

    for token in ("broken", make_jwt(uuid.uuid4())):
        response = http.post("/", json=RPC, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_rpc_of_blocked_user_is_403(http, api):
    api.user_active = False
    response = http.post("/", json=RPC, headers={"Authorization": f"Bearer {api.token}"})
    assert response.status_code == 403
