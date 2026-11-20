"""How a component creates a REST client for one user (one JWT)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from ai_tools.config import GatewaySettings
from ai_tools.gateway.client import FinanceApiClient

ApiClientFactory = Callable[[str], FinanceApiClient]


def gateway_client_factory(
    settings: GatewaySettings,
    *,
    client_class: type[FinanceApiClient] = FinanceApiClient,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ApiClientFactory:
    """``client_class`` allows an extended client (budget-agent); ``transport`` is injected by tests."""

    def create(access_token: str) -> FinanceApiClient:
        return client_class(
            base_url=settings.base_url,
            access_token=access_token,
            timeout_seconds=settings.timeout_seconds,
            transport=transport,
        )

    return create
