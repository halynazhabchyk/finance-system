"""Typed asynchronous REST client of the public API behind Traefik."""

from shared.ai_tools.gateway.client import FinanceApiClient
from shared.ai_tools.gateway.errors import GatewayError

__all__ = ["FinanceApiClient", "GatewayError"]
