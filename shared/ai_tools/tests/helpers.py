from shared.ai_tools.gateway import FinanceApiClient
from shared.ai_tools.testing import FakeFinanceApi


def api_client(api: FakeFinanceApi, token: str | None = None) -> FinanceApiClient:
    return FinanceApiClient(
        base_url="http://gateway.test",
        access_token=token if token is not None else api.token,
        transport=api.transport(),
    )
