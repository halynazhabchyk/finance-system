"""Typed asynchronous REST client of the public API behind Traefik."""

from ai_tools.gateway.client import FinanceApiClient
from ai_tools.gateway.errors import GatewayError

__all__ = ["FinanceApiClient", "GatewayError"]
