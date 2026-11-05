from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RefreshRequest(BaseModel):
    scope: Literal["daily", "monthly"]
    requested_at: datetime


class RefreshResponse(BaseModel):
    scope: Literal["daily", "monthly"]
    refreshed_reports: int
    refreshed_at: datetime
