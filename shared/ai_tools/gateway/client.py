"""REST client of the public API (Traefik) acting on behalf of one user.

Every request carries the user's JWT; ``user_id`` is never a parameter – the
services take it from the verified token (Database per Service is respected:
the AI components never touch a database).

The client exposes only the operations the AI tools and MCP resources need:
reading budgets/reports and creating categories/expenses. It deliberately has
no update/delete methods.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import jwt

from shared.ai_tools.gateway.errors import GatewayError


class AuthenticationFailed(Exception):
    """The JWT is missing, malformed, invalid or expired."""


class AccountBlocked(Exception):
    """The JWT is valid but the account is blocked."""


class FinanceApiClient:
    """Asynchronous client of ``/api/users``, ``/api/budgets`` and ``/api/reports``."""

    def __init__(
        self,
        *,
        base_url: str,
        access_token: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._access_token = access_token
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    async def __aenter__(self) -> FinanceApiClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # --- authentication -------------------------------------------------

    async def verify_current_user(self) -> uuid.UUID:
        """Check the JWT with User Service through the gateway and return ``user_id``.

        The subject is read without verifying the signature only to build the
        URL; User Service then verifies signature, expiry and ownership.
        """
        try:
            subject = jwt.decode(self._access_token, options={"verify_signature": False}).get("sub")
            user_id = uuid.UUID(str(subject))
        except (jwt.InvalidTokenError, ValueError, TypeError) as error:
            raise AuthenticationFailed("The access token is malformed.") from error
        try:
            user = await self._request("GET", f"/api/users/{user_id}")
        except GatewayError as error:
            if error.status_code in (401, 403, 404):
                raise AuthenticationFailed("The access token was rejected by User Service.") from error
            raise
        if not user.get("is_active", False):
            raise AccountBlocked("The user account is blocked.")
        return user_id

    # --- budgets --------------------------------------------------------

    async def find_budgets_by_period(self, period: str) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/budgets", params={"period": period})

    async def get_budget_summary(self, budget_id: uuid.UUID) -> dict[str, Any]:
        return await self._request("GET", f"/api/budgets/{budget_id}")

    async def create_category(self, budget_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/api/budgets/{budget_id}/categories", json=payload)

    async def create_expense(self, budget_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/api/budgets/{budget_id}/expenses", json=payload)

    # --- reports --------------------------------------------------------

    async def get_monthly_report(self, year: int, month: int) -> dict[str, Any]:
        return await self._request("GET", f"/api/reports/monthly/{year}/{month}")

    async def get_annual_report(self, year: int) -> dict[str, Any]:
        return await self._request("GET", f"/api/reports/annual/{year}")

    # --- transport ------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = await self._http.request(method, path, params=params, json=json)
        except httpx.TimeoutException as error:
            raise GatewayError.timeout() from error
        except httpx.TransportError as error:
            raise GatewayError.network() from error
        if response.is_success:
            return response.json() if response.content else None
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        raise GatewayError.from_response(response.status_code, body)
