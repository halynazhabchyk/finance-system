"""Category request and response contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import normalize_category_name, require_non_null_updates


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    limit_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_category_name(value)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    limit_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return normalize_category_name(value)

    @model_validator(mode="after")
    def validate_update_fields(self):
        require_non_null_updates(self, ("name", "limit_amount"))
        return self


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
