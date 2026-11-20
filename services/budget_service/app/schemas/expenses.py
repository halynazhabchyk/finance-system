"""Expense request and response contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import normalize_optional_text, require_non_null_updates


class ExpenseCreate(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    occurred_at: date
    description: str | None = Field(default=None, max_length=500)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class ExpenseUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    occurred_at: date | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_update_fields(self):
        # description may be cleared with null; the other fields may not.
        require_non_null_updates(self, ("category_id", "amount", "occurred_at"))
        return self


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    expense_id: uuid.UUID
    budget_id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    currency: str
    occurred_at: date
    description: str | None
    saga_status: str
    created_at: datetime
