"""Interactive A2A client: Keycloak token, Agent Card discovery, live states, follow-up answers, errors."""

import asyncio

import pytest

from a2a_chat.__main__ import parse_args, run
from a2a_chat.auth import TokenProblem, inspect_token, read_token
from a2a_chat.config import AGENTS
from a2a_chat.conversation import Conversation
from a2a_chat.session import ChatSession
from a2a_chat.tests.conftest import VALID_TOKEN
from shared.security.testing import make_token


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


# --- token (ЛР №5) -------------------------------------------------------------------------

def test_token_comes_from_the_environment_first():
    def must_not_ask(prompt):
        raise AssertionError("no prompt expected")

    assert read_token(" abc.def.ghi ", must_not_ask) == "abc.def.ghi"


def test_token_is_asked_in_a_hidden_prompt_and_bearer_prefix_is_dropped():
    assert read_token(None, lambda prompt: "Bearer abc.def.ghi") == "abc.def.ghi"


def test_missing_token_is_reported_with_instructions():
    with pytest.raises(TokenProblem, match="A2A_ACCESS_TOKEN"):
        read_token("", lambda prompt: "  ")


def test_token_claims_are_shown_without_verification():
    info = inspect_token(make_token(scopes=("budgets:read", "budgets:write"), preferred_username="student"))

    assert info.username == "student"
    assert info.scopes == {"budgets:read", "budgets:write"}
    assert 3 <= info.minutes_left() <= 5


@pytest.mark.parametrize(
    "token,message",
    [("not-a-jwt", "не JWT"), (make_token(expires_in=-60), "Строк дії токена минув"), (make_token(sub=None), "sub або exp")],
    ids=["garbage", "expired", "no-sub"],
)
def test_unusable_tokens_are_reported_before_any_request(token, message):
    with pytest.raises(TokenProblem, match=message):
        inspect_token(token)


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
    chat(lambda: remote(make_token()), console, "Додай 250 грн за листопад")

    assert any(line.startswith("[помилка]") for line in output)
    assert any("Swagger" in line for line in output)  # how to get a new token


# --- whole program -------------------------------------------------------------------------

def test_run_uses_the_token_from_the_environment_and_chats_until_exit(gateway, console, output):
    lines = iter(["Додай витрату 250 грн на продукти за листопад 2026", "вихід"])
    settings = parse_args(["--gateway", "http://gateway.test"])

    def must_not_ask(prompt):
        raise AssertionError("the token comes from A2A_ACCESS_TOKEN")

    code = asyncio.run(
        run(settings, read=lambda _: next(lines), read_secret=must_not_ask, env_token=VALID_TOKEN, console=console, transport=gateway)
    )

    text = "\n".join(output)
    assert code == 0
    assert "Токен користувача student" in text
    assert "[COMPLETED] Expense is CONFIRMED." in text
    assert VALID_TOKEN not in text  # the token is never printed


def test_run_stops_on_expired_token_without_calling_the_agent(console, output):
    import httpx

    def must_not_be_called(request):
        raise AssertionError("no request expected")

    settings = parse_args(["--gateway", "http://gateway.test"])
    code = asyncio.run(
        run(settings, read=input, read_secret=input, env_token=make_token(expires_in=-60), console=console,
            transport=httpx.MockTransport(must_not_be_called))
    )

    assert code == 1
    assert any("Строк дії токена минув" in line for line in output)


def test_report_agent_can_be_chosen():
    settings = parse_args(["--agent", "report", "--gateway", "http://localhost:8080/"])
    assert settings.agent_url == "http://localhost:8080/agents/report"
    assert settings.target.text_skill == "analyze_monthly_spending"
