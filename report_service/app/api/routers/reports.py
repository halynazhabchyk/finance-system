"""HTTP routes for monthly and annual reports."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas import AnnualReportResponse, MonthlyReportResponse
from app.services import reports as report_service

router = APIRouter(prefix="/internal/reports", tags=["reports"])


@router.get("/monthly/{year}/{month}", response_model=MonthlyReportResponse)
def get_monthly_report(year: int, month: int, current_user: CurrentUser, db: DatabaseSession):
    return report_service.get_monthly_report(db, current_user, year, month)


@router.get("/annual/{year}", response_model=AnnualReportResponse)
def get_annual_report(
    year: Annotated[int, Path(ge=1, le=9999)],
    current_user: CurrentUser,
    db: DatabaseSession,
):
    return report_service.get_annual_report(db, current_user, year)
