import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas import (
    AnnualReportResponse,
    MonthlyReportResponse,
    RefreshRequest,
    RefreshResponse,
)
from app.services import reports as report_service


router = APIRouter(prefix="/internal/reports", tags=["reports"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]


@router.get("/{user_id}/monthly/{year}/{month}", response_model=MonthlyReportResponse)
def get_monthly_report(
    user_id: uuid.UUID,
    year: int,
    month: int,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    if current_user != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return report_service.get_monthly_report(db, user_id, year, month)


@router.get("/{user_id}/annual/{year}", response_model=AnnualReportResponse)
def get_annual_report(
    user_id: uuid.UUID,
    year: Annotated[int, Path(ge=1, le=9999)],
    current_user: CurrentUser,
    db: DatabaseSession,
):
    if current_user != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return report_service.get_annual_report(db, user_id, year)


@router.post("/refresh", response_model=RefreshResponse)
def refresh_reports(
    payload: RefreshRequest,
    db: DatabaseSession,
) -> RefreshResponse:
    return report_service.refresh_reports(
        db,
        payload.scope,
        payload.requested_at,
    )
