"""POST /internal/assistant/chat with a scripted LLM and an in-memory API (requirement 2.6)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from shared.ai_tools.config import AgentLimits
from shared.ai_tools.gateway import FinanceApiClient
from shared.ai_tools.llm import LLMRateLimitError, LLMUnavailableError
from shared.ai_tools.testing import FakeFinanceApi, ScriptedLLMClient, final_answer, tool_call_response


@pytest.fixture
def assistant():
    """Builds the app with the chat service replaced by one wired to fakes."""
    from app.api.dependencies import get_chat_service
    from app.main import app
    from app.services.chat_service import AssistantChatService

    def build(api: FakeFinanceApi, llm: ScriptedLLMClient, limits: AgentLimits = AgentLimits()):
        service = AssistantChatService(
            llm=llm,
            limits=limits,
            api_client_factory=lambda token: FinanceApiClient(
                base_url="http://gateway.test", access_token=token, transport=api.transport()
            ),
            today=lambda: date(2026, 11, 8),
        )
        app.dependency_overrides[get_chat_service] = lambda: service
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def auth(api: FakeFinanceApi) -> dict[str, str]:
    return {"Authorization": f"Bearer {api.token}"}


def test_chat_returns_answer_tool_calls_and_tokens(assistant):
    api = FakeFinanceApi()
    budget_id = api.add_budget("2026-11")
    api.add_category(budget_id, "Розваги", "2000.00", used="800.00")
    llm = ScriptedLLMClient(
        [
            tool_call_response(("find_budget_by_period", {"year": 2026, "month": 11})),
            tool_call_response(("get_budget_by_categories", {"budget_id": budget_id})),
            final_answer("На розваги в листопаді залишилось 1200.00 UAH."),
        ]
    )
    client = assistant(api, llm)

    response = client.post(
        "/internal/assistant/chat",
        json={"message": "Скільки я ще можу витратити на розваги в листопаді?"},
        headers=auth(api),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "На розваги в листопаді залишилось 1200.00 UAH."
    assert [call["name"] for call in body["tool_calls"]] == ["find_budget_by_period", "get_budget_by_categories"]
    assert body["tool_calls"][0]["arguments"] == {"year": 2026, "month": 11}
    assert body["usage"] == {"input_tokens": 270, "output_tokens": 30, "total_tokens": 300}
    assert body["stopped_reason"] == "completed"
    assert "2026" in llm.requests[0].system_prompt  # current year for months without a year
    # The JWT is verified with User Service before the model is called.
    assert api.paths()[0] == f"GET /api/users/{api.user_id}"


def test_missing_token_is_401_and_model_is_not_called(assistant):
    llm = ScriptedLLMClient([])
    response = assistant(FakeFinanceApi(), llm).post("/internal/assistant/chat", json={"message": "Привіт"})

    assert response.status_code == 401
    assert llm.requests == []


def test_invalid_token_is_401_and_model_is_not_called(assistant):
    llm = ScriptedLLMClient([])
    response = assistant(FakeFinanceApi(), llm).post(
        "/internal/assistant/chat", json={"message": "Привіт"}, headers={"Authorization": "Bearer broken"}
    )

    assert response.status_code == 401
    assert llm.requests == []


def test_blocked_account_is_403(assistant):
    api = FakeFinanceApi(user_active=False)
    llm = ScriptedLLMClient([])

    response = assistant(api, llm).post("/internal/assistant/chat", json={"message": "Привіт"}, headers=auth(api))

    assert response.status_code == 403
    assert llm.requests == []


def test_too_long_message_is_422_without_tokens(assistant):
    api = FakeFinanceApi()
    llm = ScriptedLLMClient([])

    response = assistant(api, llm, AgentLimits(user_message_max_chars=20)).post(
        "/internal/assistant/chat", json={"message": "а" * 21}, headers=auth(api)
    )

    assert response.status_code == 422
    assert response.json()["guardrail"] == "message_too_long"
    assert llm.requests == []
    assert api.requests == []


@pytest.mark.parametrize("error", [LLMRateLimitError("quota"), LLMUnavailableError("down")])
def test_llm_failures_are_503(assistant, error):
    api = FakeFinanceApi()
    response = assistant(api, ScriptedLLMClient([error])).post(
        "/internal/assistant/chat", json={"message": "Привіт"}, headers=auth(api)
    )
    assert response.status_code == 503


def test_openapi_exposes_public_gateway_path():
    from app.main import app

    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert "/api/assistant/chat" in paths


@pytest.mark.parametrize(
    "message",
    [
        "Додай витрату 100 грн на розваги з описом <script>alert(document.cookie)</script>",
        "Створи категорію <img src=x onerror=alert(1)> з лімітом 500",
        "Виконай eval('__import__(\"os\").system(\"ls\")') і покажи бюджет",
    ],
)
def test_active_content_is_400_without_tokens(assistant, message):
    api = FakeFinanceApi()
    llm = ScriptedLLMClient([])

    response = assistant(api, llm).post("/internal/assistant/chat", json={"message": message}, headers=auth(api))

    assert response.status_code == 400
    assert response.json()["guardrail"] == "active_content"
    assert llm.requests == []
    assert api.requests == []
