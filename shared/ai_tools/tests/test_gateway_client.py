"""FinanceApiClient: JWT header, timeouts, HTTP errors -> messages for the LLM (requirement 2.1)."""

import asyncio
import uuid

import httpx
import pytest

from shared.ai_tools.gateway import FinanceApiClient, GatewayError
from shared.ai_tools.gateway.client import AccountBlocked, AuthenticationFailed
from shared.ai_tools.testing import FakeFinanceApi, make_jwt
from shared.ai_tools.tests.helpers import api_client


def run(coro):
    return asyncio.run(coro)


def test_requests_carry_bearer_token_and_go_to_gateway():
    api = FakeFinanceApi()
    api.add_budget("2026-11")

    async def scenario():
        async with api_client(api) as client:
            return await client.find_budgets_by_period("2026-11")

    budgets = run(scenario())

    request = api.requests[0]
    assert request.headers["Authorization"] == f"Bearer {api.token}"
    assert str(request.url) == "http://gateway.test/api/budgets?period=2026-11"
    assert len(budgets) == 1


def test_client_has_timeouts():
    client = FinanceApiClient(base_url="http://gateway.test", access_token="t", timeout_seconds=3.5)
    assert client._http.timeout.read == 3.5
    run(client.aclose())


@pytest.mark.parametrize(
    "status,fragment",
    [
        (401, "Authentication failed"),
        (403, "Access denied"),
        (404, "Not found"),
        (409, "Conflict"),
        (422, "rejected the data"),
        (500, "temporarily unavailable (HTTP 500)"),
        (503, "temporarily unavailable (HTTP 503)"),
    ],
)
def test_http_errors_become_llm_messages(status, fragment):
    api = FakeFinanceApi(fail_with=status)

    async def scenario():
        async with api_client(api) as client:
            await client.get_budget_summary(uuid.uuid4())

    with pytest.raises(GatewayError) as raised:
        run(scenario())

    assert raised.value.status_code == status
    assert fragment in raised.value.llm_message
    assert api.token not in raised.value.llm_message


def test_validation_detail_list_is_summarized():
    error = GatewayError.from_response(
        422, {"detail": [{"loc": ["body", "amount"], "msg": "Input should be greater than 0"}]}
    )
    assert "amount: Input should be greater than 0" in error.llm_message


@pytest.mark.parametrize(
    "exception,fragment",
    [(httpx.ReadTimeout("slow"), "did not respond in time"), (httpx.ConnectError("down"), "unreachable")],
)
def test_timeouts_and_network_errors(exception, fragment):
    def handler(request):
        raise exception

    async def scenario():
        async with FinanceApiClient(
            base_url="http://gateway.test", access_token="t", transport=httpx.MockTransport(handler)
        ) as client:
            await client.get_monthly_report(2026, 11)

    with pytest.raises(GatewayError) as raised:
        run(scenario())
    assert raised.value.status_code is None
    assert fragment in raised.value.llm_message


def test_verify_current_user_returns_user_id_from_user_service():
    api = FakeFinanceApi()

    async def scenario():
        async with api_client(api) as client:
            return await client.verify_current_user()

    assert run(scenario()) == api.user_id
    assert api.paths() == [f"GET /api/users/{api.user_id}"]


def test_blocked_account_is_detected():
    api = FakeFinanceApi(user_active=False)

    async def scenario():
        async with api_client(api) as client:
            await client.verify_current_user()

    with pytest.raises(AccountBlocked):
        run(scenario())


@pytest.mark.parametrize("token_factory", [lambda api: "not-a-jwt", lambda api: make_jwt(uuid.uuid4())])
def test_malformed_or_foreign_token_is_rejected(token_factory):
    api = FakeFinanceApi()

    async def scenario():
        async with api_client(api, token_factory(api)) as client:
            await client.verify_current_user()

    with pytest.raises(AuthenticationFailed):
        run(scenario())
