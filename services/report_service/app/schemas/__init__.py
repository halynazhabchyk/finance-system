"""Pydantic response contracts for Report Service."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict



class CategoryReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category_name: str
    limit_amount: Decimal
    total_expenses: Decimal
    currency: str
    percentage: Decimal


class MonthlyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    report_id: uuid.UUID
    user_id: uuid.UUID
    period: str
    month: int
    period_start: date
    total_budget: Decimal
    total_expenses: Decimal
    remaining: Decimal
    remaining_amount: Decimal
    currency: str
    generated_at: datetime
    refreshed_at: datetime
    categories: list[CategoryReport]


class AnnualReportResponse(BaseModel):
    report_id: uuid.UUID
    user_id: uuid.UUID
    period: str
    year: int
    total_budget: Decimal
    total_expenses: Decimal
    remaining: Decimal
    remaining_amount: Decimal
    currency: str
    generated_at: datetime
    months: list[MonthlyReportResponse]


__all__ = [
    "AnnualReportResponse",
    "CategoryReport",
    "MonthlyReportResponse",
]
