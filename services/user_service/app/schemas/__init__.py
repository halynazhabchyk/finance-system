"""Pydantic request and response contracts for User Service."""

from app.schemas.users import UserResponse, UserUpdateName

__all__ = [
    "UserResponse",
    "UserUpdateName",
]
