import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories import reports as repository


REPORT_NAMESPACE = uuid.UUID("2f2cbe4c-42d7-4e51-98a4-6fb95d0dd8fd")
MONEY_QUANTUM = Decimal("0.01")


def _category_reports(report, categories) -> list[dict]:
    total_expenses = Decimal(report.total_expenses)
    category_total = sum(
        (Decimal(category.total_expenses) for category in categories),
        Decimal("0.00"),
    )
    if category_total != total_expenses:
        raise HTTPException(
            status_code=422,
            detail="Category expense totals do not match the report total.",
        )
    result = []
    for category in categories:
        percentage = (
            (Decimal(category.total_expenses) * Decimal("100") / total_expenses)
            if total_expenses
            else Decimal("0")
        ).quantize(MONEY_QUANTUM)
        result.append(
            {
                "category_name": category.category_name,
                "limit_amount": category.limit_amount,
                "total_expenses": category.total_expenses,
                "currency": report.currency,
                "percentage": percentage,
            }
        )

    if total_expenses and result:
        difference = Decimal("100.00") - sum(
            (item["percentage"] for item in result),
            Decimal("0.00"),
        )
        result[-1]["percentage"] += difference
    return result


def _monthly_response(report, categories) -> dict:
    categories = _category_reports(report, categories)
    generated_at = report.refreshed_at
    return {
        "report_id": report.report_id,
        "user_id": report.user_id,
        "period": report.period_start.strftime("%Y-%m"),
        "month": report.period_start.month,
        "period_start": report.period_start,
        "total_budget": report.total_budget,
        "total_expenses": report.total_expenses,
        "remaining": report.remaining_amount,
        "remaining_amount": report.remaining_amount,
        "currency": report.currency,
        "generated_at": generated_at,
        "refreshed_at": generated_at,
        "categories": categories,
    }


def refresh_reports(db: Session, scope: str, requested_at: datetime) -> dict:
    refreshed_at = requested_at.astimezone(timezone.utc)
    refreshed_count = repository.refresh_reports(db, refreshed_at)
    db.commit()
    return {
        "scope": scope,
        "refreshed_reports": refreshed_count,
        "refreshed_at": refreshed_at,
    }


def get_monthly_report(db: Session, user_id: uuid.UUID, year: int, month: int) -> dict:
    try:
        period_start = date(year, month, 1)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="month must be between 1 and 12") from error
    report = repository.get_month(db, user_id, period_start)
    if report is None:
        raise HTTPException(status_code=404, detail="Monthly report is not available yet.")
    return _monthly_response(
        report,
        repository.get_categories(db, report.report_id),
    )


def get_annual_report(db: Session, user_id: uuid.UUID, year: int) -> dict:
    months = repository.get_months(db, user_id, year)
    if not months:
        raise HTTPException(status_code=404, detail="Annual report is not available yet.")
    currencies = {month.currency for month in months}
    if len(currencies) != 1:
        raise HTTPException(
            status_code=422,
            detail="Reports for one year must use a single currency.",
        )
    generated_at = max(month.refreshed_at for month in months)
    total_budget = sum((month.total_budget for month in months), Decimal("0.00"))
    total_expenses = sum((month.total_expenses for month in months), Decimal("0.00"))
    remaining = total_budget - total_expenses
    return {
        "report_id": uuid.uuid5(REPORT_NAMESPACE, f"{user_id}:{year}"),
        "user_id": user_id,
        "period": str(year),
        "year": year,
        "total_budget": total_budget,
        "total_expenses": total_expenses,
        "remaining": remaining,
        "remaining_amount": remaining,
        "currency": months[0].currency,
        "generated_at": generated_at,
        "months": [_monthly_response(month, repository.get_categories(db, month.report_id)) for month in months],
    }
