"""Validation helpers shared by request schemas."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel


def require_non_null_updates(model: BaseModel, non_nullable: Iterable[str]) -> None:
    """A PATCH body must change something and must not set required fields to null."""
    if not model.model_fields_set:
        raise ValueError("At least one field must be provided")
    for field_name in non_nullable:
        if field_name in model.model_fields_set and getattr(model, field_name) is None:
            raise ValueError(f"{field_name} cannot be null")


def normalize_category_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Category name cannot be empty")
    return value


def normalize_optional_text(value: str | None) -> str | None:
    """Trim the text; an empty string means "no value"."""
    if value is None:
        return None
    return value.strip() or None
