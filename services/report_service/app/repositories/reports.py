import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import MonthlyReport, ProcessedEvent, ReportCategoryTotal


def get_month(db: Session, user_id: uuid.UUID, period_start: date):
    return db.scalar(
        select(MonthlyReport).where(
            MonthlyReport.user_id == user_id,
            MonthlyReport.period_start == period_start,
        )
    )


def get_months(db: Session, user_id: uuid.UUID, year: int) -> list[MonthlyReport]:
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    return list(db.scalars(
        select(MonthlyReport)
        .where(MonthlyReport.user_id == user_id, MonthlyReport.period_start >= start, MonthlyReport.period_start < end)
        .order_by(MonthlyReport.period_start)
    ).all())


def get_categories(db: Session, report_id: uuid.UUID) -> list[ReportCategoryTotal]:
    return list(db.scalars(
        select(ReportCategoryTotal).where(ReportCategoryTotal.report_id == report_id).order_by(ReportCategoryTotal.category_name)
    ).all())


def event_processed(db: Session, event_id: uuid.UUID) -> bool:
    return db.get(ProcessedEvent, event_id) is not None


def mark_event_processed(
    db: Session,
    event_id: uuid.UUID,
    event_type: str,
    received_at: datetime,
) -> None:
    """Insert the inbox row; committed together with the business change."""
    db.add(
        ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            received_at=received_at,
            status="PROCESSED",
        )
    )


def refresh_reports(
    db: Session,
    refreshed_at: datetime,
    period_start: date,
    period_end: date,
) -> int:
    statement = update(MonthlyReport).values(
        remaining_amount=MonthlyReport.total_budget - MonthlyReport.total_expenses,
        refreshed_at=refreshed_at,
    ).where(
        MonthlyReport.period_start >= period_start,
        MonthlyReport.period_start <= period_end,
    )
    result = db.execute(statement)
    return result.rowcount or 0


def apply_budget_snapshot(db: Session, event: dict) -> None:
    period_start = date.fromisoformat(event["period_start"])
    aggregate_version = int(event["aggregate_version"])
    report = get_month(db, uuid.UUID(event["user_id"]), period_start)
    if report is not None and aggregate_version <= report.source_aggregate_version:
        return
    if report is None:
        report = MonthlyReport(
            user_id=uuid.UUID(event["user_id"]),
            period_start=period_start,
            total_budget=Decimal(event["total_budget"]),
            total_expenses=Decimal("0.00"),
            remaining_amount=Decimal(event["total_budget"]),
            currency=event["currency"],
            source_aggregate_version=aggregate_version,
        )
        db.add(report)
        db.flush()
    else:
        report.total_budget = Decimal(event["total_budget"])
        report.currency = event["currency"]
        report.source_aggregate_version = aggregate_version

    report.total_expenses = sum(
        (Decimal(expense["amount"]) for expense in event.get("expenses", [])),
        Decimal("0.00"),
    )
    report.remaining_amount = report.total_budget - report.total_expenses
    for category in list(report.categories):
        db.delete(category)
    db.flush()
    for category in event.get("categories", []):
        report.categories.append(
            ReportCategoryTotal(
                category_name=category["name"],
                limit_amount=Decimal(category["limit_amount"]),
                total_expenses=Decimal(category["total_expenses"]),
            )
        )


def apply_budget_deleted(db: Session, event: dict) -> None:
    report = get_month(
        db,
        uuid.UUID(event["user_id"]),
        date.fromisoformat(event["period_start"]),
    )
    if (
        report is not None
        and int(event["aggregate_version"]) > report.source_aggregate_version
    ):
        db.delete(report)
