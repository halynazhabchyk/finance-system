"""Pydantic request and response contracts for Budget Service."""

import uuid
import calendar

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field_name in ("period_start", "period_end", "total_amount"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
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


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    limit_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category name cannot be empty")
        return value


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    limit_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field_name in ("name", "limit_amount"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Category name cannot be empty")
        return value


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category_id: uuid.UUID
    budget_id: uuid.UUID
    name: str
    limit_amount: Decimal
    currency: str


class CategorySummary(BaseModel):
    category_id: uuid.UUID
    budget_id: uuid.UUID
    name: str
    limit_amount: Decimal
    currency: str
    used_amount: Decimal
    available_amount: Decimal
    limit_exceeded: bool


class ExpenseCreate(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    occurred_at: date
    description: str | None = Field(default=None, max_length=500)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExpenseUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    occurred_at: date | None = None
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field_name in ("category_id", "amount", "occurred_at"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    expense_id: uuid.UUID
    budget_id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    currency: str
    occurred_at: date
    description: str | None
    created_at: datetime


class BudgetSummary(BaseModel):
    budget: BudgetResponse
    used_amount: Decimal
    available_amount: Decimal
    categories: list[CategorySummary]
    expenses: list[ExpenseResponse]
    service: str
    instance_id: str