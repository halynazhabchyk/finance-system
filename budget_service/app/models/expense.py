import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

EXPENSE_PENDING = "PENDING"
EXPENSE_CONFIRMED = "CONFIRMED"
EXPENSE_CANCELLED = "CANCELLED"
if TYPE_CHECKING:
    from app.models.budget import Budget
    from app.models.category import Category


class Expense(Base):
    __tablename__ = "expenses"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_expenses_amount_positive",
        ),
        CheckConstraint(
            "saga_status IN ('PENDING', 'CONFIRMED', 'CANCELLED')",
            name="ck_expenses_saga_status",
        ),
        ForeignKeyConstraint(
            ["budget_id", "category_id"],
            ["categories.budget_id", "categories.category_id"],
            ondelete="RESTRICT",
            name="fk_expenses_budget_category",
        ),
    )

    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("budgets.budget_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    occurred_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # SAGA lifecycle: PENDING until Report Service confirms, CANCELLED after
    # compensation (DLQ or timeout). Cancelled rows are kept as history.
    saga_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EXPENSE_PENDING,
        server_default=EXPENSE_CONFIRMED,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    budget: Mapped["Budget"] = relationship(
        back_populates="expenses",
    )

    category: Mapped["Category"] = relationship(
        back_populates="expenses",
    )

    @property
    def currency(self) -> str:
        """Return the currency inherited from the owning budget."""
        return self.budget.currency