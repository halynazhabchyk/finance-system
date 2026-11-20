"""REST operations available only to the deterministic skills of budget-agent."""

from __future__ import annotations

import uuid
from typing import Any

from shared.ai_tools.gateway import FinanceApiClient


class BudgetAgentApiClient(FinanceApiClient):
    async def create_budget(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/budgets", json=payload)

    async def update_expense(
        self, budget_id: uuid.UUID, expense_id: uuid.UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request("PATCH", f"/api/budgets/{budget_id}/expenses/{expense_id}", json=payload)

    async def delete_expense(self, budget_id: uuid.UUID, expense_id: uuid.UUID) -> None:
        await self._request("DELETE", f"/api/budgets/{budget_id}/expenses/{expense_id}")

    async def get_expense_saga(self, budget_id: uuid.UUID, expense_id: uuid.UUID) -> dict[str, Any]:
        return await self._request("GET", f"/api/budgets/{budget_id}/expenses/{expense_id}/saga")
