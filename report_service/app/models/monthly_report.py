"""Monthly report read model owned by Report Service."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.report_category_total import ReportCategoryTotal


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period_start",
            name="uq_monthly_reports_user_period",
        ),
        CheckConstraint(
            "total_budget >= 0",
            name="ck_monthly_reports_budget_non_negative",
        ),
        CheckConstraint(
            "total_expenses >= 0",
            name="ck_monthly_reports_expenses_non_negative",
        ),
        CheckConstraint(
            "remaining_amount = total_budget - total_expenses",
            name="ck_monthly_reports_remaining_consistent",
        ),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True, default=uuid.uuid4,)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    total_budget: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    total_expenses: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="UAH",
        server_default="UAH",
    )

    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    categories: Mapped[list["ReportCategoryTotal"]] = relationship(
        "ReportCategoryTotal",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )