"""Budget request and response contracts."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.categories import CategorySummary
from app.schemas.expenses import ExpenseResponse
from app.schemas.validators import require_non_null_updates


class BudgetCreate(BaseModel):
    period_start: date
    period_end: date
    total_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="UAH", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        last_day = calendar.monthrange(self.period_start.year, self.period_start.month)[1]
        if (
            self.period_start.day != 1
            or self.period_end.year != self.period_start.year
            or self.period_end.month != self.period_start.month
            or self.period_end.day != last_day
        ):
            raise ValueError("A budget period must cover one complete calendar month")
        return self


class BudgetUpdate(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    total_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def validate_update_fields(self):
        require_non_null_updates(self, ("period_start", "period_end", "total_amount"))
        return self


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    budget_id: uuid.UUID
    user_id: uuid.UUID
    period_start: date
    period_end: date
    total_amount: Decimal
    currency: str
    created_at: datetime


class BudgetSummary(BaseModel):
    budget: BudgetResponse
    used_amount: Decimal
    available_amount: Decimal
    categories: list[CategorySummary]
    expenses: list[ExpenseResponse]
    service: str
    instance_id: str
