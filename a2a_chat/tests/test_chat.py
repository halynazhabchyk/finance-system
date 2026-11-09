"""Interactive A2A client: login, Agent Card discovery, live states, follow-up answers, errors."""

import asyncio

import httpx
import pytest

from a2a_chat.__main__ import parse_args, run
from a2a_chat.auth import LoginFailed, login
from a2a_chat.config import AGENTS
from a2a_chat.conversation import Conversation
from a2a_chat.session import ChatSession
from a2a_chat.tests.conftest import EMAIL, PASSWORD


def chat(remote, console, *lines):
    async def scenario():
        async with remote() as client:
            session = ChatSession(remote=client, target=AGENTS["budget"], console=console)
            await session.start()
            results = [await session.handle(line) for line in lines]
            return session, results

    return asyncio.run(scenario())


# --- conversation memory -------------------------------------------------------------------

def test_follow_up_answer_is_sent_with_the_open_request():
    conversation = Conversation()
    assert conversation.compose("Додай 250 грн на продукти") == "Додай 250 грн на продукти"

    conversation.record("Додай 250 грн на продукти", "INPUT_REQUIRED", "За який місяць?")
    assert conversation.awaiting_answer
    assert conversation.compose("листопад 2026") == (
        "Додай 250 грн на продукти\nУточнення агента: За який місяць?\nВідповідь: листопад 2026"
    )

    conversation.record("…", "COMPLETED", "done")
    assert not conversation.awaiting_answer
    assert conversation.compose("Нове питання") == "Нове питання"


# --- login ---------------------------------------------------------------------------------

def test_login_returns_the_token(gateway):
    token = asyncio.run(login("http://gateway.test", EMAIL, PASSWORD, transport=gateway))
    assert token == "valid-token"


def test_wrong_password_is_reported(gateway):
    with pytest.raises(LoginFailed, match="Невірний email або пароль"):
        asyncio.run(login("http://gateway.test", EMAIL, "wrong", transport=gateway))


@pytest.mark.parametrize(
    "email,password",
    [("", PASSWORD), ("   ", PASSWORD), (EMAIL, "")],
)
def test_empty_credentials_are_rejected_without_a_request(email, password):
    def must_not_be_called(request):
        raise AssertionError("no request expected")

    with pytest.raises(LoginFailed, match="Вкажіть email і пароль"):
        asyncio.run(login("http://gateway.test", email, password, transport=httpx.MockTransport(must_not_be_called)))


@pytest.mark.parametrize(
    "response,message",
    [
        (httpx.Response(403, json={"detail": "inactive"}), "заблоковано"),
        (httpx.Response(404, text="404 page not found"), "не зареєстрований у Consul"),
        (httpx.Response(503, text="Service Unavailable"), "тимчасово недоступний"),
        (httpx.Response(200, text="<html>proxy page</html>"), "не у форматі JSON"),
        (httpx.Response(200, json={"token_type": "bearer"}), "не повернув access_token"),
        (httpx.Response(200, json={"access_token": 123}), "не повернув access_token"),
    ],
)
def test_unexpected_replies_become_clear_messages(response, message):
    with pytest.raises(LoginFailed, match=message):
        asyncio.run(login("http://gateway.test", EMAIL, PASSWORD, transport=httpx.MockTransport(lambda _: response)))


def test_timeout_is_reported():
    def slow(request):
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(LoginFailed, match="не відповів"):
        asyncio.run(login("http://gateway.test", EMAIL, PASSWORD, transport=httpx.MockTransport(slow)))


def test_unreachable_gateway_is_reported():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LoginFailed, match="недоступний"):
        asyncio.run(login("http://gateway.test", EMAIL, PASSWORD, transport=httpx.MockTransport(refuse)))


# --- session -------------------------------------------------------------------------------

def test_agent_card_is_shown_on_start(remote, console, output):
    chat(remote, console)

    text = "\n".join(output)
    assert "Agent Card: budget-agent 1.0.0" in text
    assert "register_expense" in text
    assert "bearerAuth" in text


def test_message_shows_live_states_and_artifact(remote, console, output, received_texts):
    chat(remote, console, "Додай витрату 250 грн на продукти за 8 листопада 2026")

    text = "\n".join(output)
    assert "[WORKING] Expense accepted with saga_status PENDING" in text
    assert "[COMPLETED] Expense is CONFIRMED." in text
    assert "Артефакт «expense»" in text and '"saga_status": "CONFIRMED"' in text
    assert received_texts == ["Додай витрату 250 грн на продукти за 8 листопада 2026"]


def test_question_of_the_agent_is_answered_in_the_next_message(remote, console, output, received_texts):
    session, _ = chat(remote, console, "Додай 250 грн на продукти", "листопад 2026")

    text = "\n".join(output)
    assert "[INPUT_REQUIRED] За який місяць додати витрату?" in text
    assert "[COMPLETED] Expense is CONFIRMED." in text
    # The agent keeps no history: the client resent the request together with the answer.
    assert received_texts[1].startswith("Додай 250 грн на продукти\nУточнення агента: За який місяць додати витрату?")
    assert received_texts[1].endswith("Відповідь: листопад 2026")
    assert not session.awaiting_answer


def test_commands(remote, console, output, received_texts):
    session, results = chat(remote, console, "Додай 250 грн", "новий", "картка", "допомога", "вихід")

    assert results == [True, True, True, True, False]
    assert not session.awaiting_answer  # «новий» dropped the open request
    assert received_texts == ["Додай 250 грн"]  # commands are not sent to the agent
    assert sum("Agent Card:" in line for line in output) == 2


def test_rejected_token_is_shown_as_an_error(remote, console, output):
    chat(lambda: remote("expired-token"), console, "Додай 250 грн за листопад")

    assert any(line.startswith("[помилка]") for line in output)


# --- whole program -------------------------------------------------------------------------

def test_run_logs_in_and_chats_until_exit(gateway, console, output):
    lines = iter(["Додай витрату 250 грн на продукти за листопад 2026", "вихід"])
    settings = parse_args(["--gateway", "http://gateway.test", "--email", EMAIL])

    code = asyncio.run(
        run(settings, read=lambda _: next(lines), read_password=lambda _: PASSWORD, console=console, transport=gateway)
    )

    text = "\n".join(output)
    assert code == 0
    assert f"Вхід виконано: {EMAIL}" in text
    assert "[COMPLETED] Expense is CONFIRMED." in text
    assert PASSWORD not in text  # the password is never printed


def test_run_stops_on_wrong_password(gateway, console, output):
    settings = parse_args(["--gateway", "http://gateway.test", "--email", EMAIL])

    code = asyncio.run(run(settings, read=input, read_password=lambda _: "wrong", console=console, transport=gateway))

    assert code == 1
    assert "[помилка] Невірний email або пароль." in output


def test_report_agent_can_be_chosen():
    settings = parse_args(["--agent", "report", "--gateway", "http://localhost:8080/"])
    assert settings.agent_url == "http://localhost:8080/agents/report"
    assert settings.target.text_skill == "analyze_monthly_spending"
