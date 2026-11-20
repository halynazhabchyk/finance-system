import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserUpdateName(BaseModel):
    """Schema for updating user's name."""

    user_name: str = Field(min_length=2, max_length=100)


class UserResponse(BaseModel):
    """Schema for returning user information."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    user_name: str
    email: EmailStr
    created_at: datetime
    is_active: bool