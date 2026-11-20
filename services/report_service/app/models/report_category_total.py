"""Category totals read model owned by Report Service."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
if TYPE_CHECKING:
    from app.models.monthly_report import MonthlyReport



class ReportCategoryTotal(Base):
    __tablename__ = "report_category_totals"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "category_name",
            name="uq_report_category_name",
        ),
        CheckConstraint(
            "limit_amount > 0",
            name="ck_report_category_limit_positive",
        ),
        CheckConstraint(
            "total_expenses >= 0",
            name="ck_report_category_expenses_non_negative",
        ),
        CheckConstraint(
            "length(trim(category_name)) > 0",
            name="ck_report_category_name_not_empty",
        ),
    )

    category_total_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "monthly_reports.report_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    category_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    limit_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    total_expenses: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    report: Mapped["MonthlyReport"] = relationship(
        back_populates="categories",
    )