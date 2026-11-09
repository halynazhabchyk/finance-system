"""Arguments of the deterministic skills (validated before any API call)."""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from shared.ai_tools.tools.schemas import (
    Month,
    PositiveMoney,
    SafeDescription,
    SafeName,
    ToolArguments,
    Year,
)


class CreateBudgetArgs(ToolArguments):
    action: Literal["create_budget"]
    year: Year
    month: Month
    total_amount: PositiveMoney
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "UAH"

    def to_payload(self) -> dict[str, str]:
        last_day = calendar.monthrange(self.year, self.month)[1]
        return {
            "period_start": date(self.year, self.month, 1).isoformat(),
            "period_end": date(self.year, self.month, last_day).isoformat(),
            "total_amount": str(self.total_amount),
            "currency": self.currency,
        }


class CreateCategoryAction(ToolArguments):
    action: Literal["create_category"]
    budget_id: uuid.UUID
    name: SafeName
    limit_amount: PositiveMoney


ManageBudgetArgs = Annotated[CreateBudgetArgs | CreateCategoryAction, Field(discriminator="action")]


class ExpenseChanges(ToolArguments):
    category_id: uuid.UUID | None = None
    amount: PositiveMoney | None = None
    occurred_at: date | None = None
    description: SafeDescription | None = None

    def to_payload(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.model_dump(exclude_none=True).items()}


class ChangeExpenseArgs(ToolArguments):
    action: Literal["update", "delete"]
    budget_id: uuid.UUID
    expense_id: uuid.UUID
    changes: ExpenseChanges | None = None
    confirm: bool = False

    @model_validator(mode="after")
    def changes_match_action(self):
        if self.action == "update" and (self.changes is None or not self.changes.to_payload()):
            raise ValueError("'update' requires at least one field in 'changes'")
        if self.action == "delete" and self.changes is not None:
            raise ValueError("'delete' does not accept 'changes'")
        return self
