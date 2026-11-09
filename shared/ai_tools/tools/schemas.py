"""Pydantic schemas of tool arguments, validated before any API call.

``extra="forbid"`` rejects unknown arguments, so a model cannot smuggle in
``user_id`` or other fields: the user is always taken from the verified JWT.
"""

from __future__ import annotations

import unicodedata
import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

from shared.ai_tools.guardrails.injection import find_injection_rules
from shared.ai_tools.guardrails.markup import find_active_content_rules

MIN_YEAR = 2000
MAX_YEAR = 2100
MAX_AMOUNT_DIGITS = 14  # same precision as NUMERIC(14, 2) in Budget Service
NAME_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 500


def _reject_control_characters(value: str) -> str:
    if any(unicodedata.category(char) in {"Cc", "Cf"} for char in value):
        raise ValueError("must not contain control or invisible formatting characters")
    return value


def _reject_instructions(value: str) -> str:
    # Stored names/descriptions are shown to models later; do not let a tool persist an injection.
    if find_injection_rules(value):
        raise ValueError("looks like an instruction to the assistant (possible prompt injection)")
    return value


def _reject_active_content(value: str) -> str:
    # Names/descriptions are rendered by clients later; do not store markup, scripts or code (stored XSS).
    if find_active_content_rules(value):
        raise ValueError("must not contain HTML markup, scripts, dangerous links or program code")
    return value


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _money_from_llm(value: object) -> object:
    # Models send numbers as JSON floats; str() keeps the value as written (250.5 -> "250.5").
    return str(value) if isinstance(value, float) else value


# Constraints come first so they become a native constrained type (and a proper JSON schema);
# the BeforeValidator wraps it and runs before the constraints are checked.
SafeName = Annotated[
    str,
    Field(min_length=1, max_length=NAME_MAX_LENGTH, description="Category name."),
    AfterValidator(_reject_control_characters),
    AfterValidator(_reject_instructions),
    AfterValidator(_reject_active_content),
    BeforeValidator(_strip),
]
SafeDescription = Annotated[
    str,
    Field(min_length=1, max_length=DESCRIPTION_MAX_LENGTH),
    AfterValidator(_reject_control_characters),
    AfterValidator(_reject_instructions),
    AfterValidator(_reject_active_content),
    BeforeValidator(_strip),
]
PositiveMoney = Annotated[
    Decimal,
    Field(gt=0, max_digits=MAX_AMOUNT_DIGITS, decimal_places=2),
    BeforeValidator(_money_from_llm),
]
Year = Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR, description=f"Year, {MIN_YEAR}-{MAX_YEAR}.")]
Month = Annotated[int, Field(ge=1, le=12, description="Month number, 1-12.")]


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FindBudgetByPeriodArgs(ToolArguments):
    year: Year
    month: Month

    @property
    def period(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


class GetBudgetByCategoriesArgs(ToolArguments):
    budget_id: uuid.UUID = Field(description="budget_id returned by find_budget_by_period.")


class CreateCategoryArgs(ToolArguments):
    budget_id: uuid.UUID = Field(description="budget_id of the budget.")
    name: SafeName
    limit_amount: PositiveMoney = Field(description="Monthly limit of the category, > 0, two decimals.")


class CreateExpenseArgs(ToolArguments):
    budget_id: uuid.UUID = Field(description="budget_id of the budget.")
    category_id: uuid.UUID = Field(description="category_id from get_budget_by_categories or create_category.")
    amount: PositiveMoney = Field(description="Expense amount, > 0, two decimals.")
    occurred_at: date = Field(description="Date of the expense, YYYY-MM-DD, inside the budget month.")
    description: SafeDescription | None = Field(default=None, description="Optional short description.")


class GetMonthlyReportArgs(ToolArguments):
    year: Year
    month: Month
