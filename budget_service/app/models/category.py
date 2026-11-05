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
    from app.models.budget import Budget
    from app.models.expense import Expense



class Category(Base):
    __tablename__ = "categories"

    __table_args__ = (
        UniqueConstraint(
            "budget_id",
            "name",
            name="uq_categories_budget_name",
        ),
        UniqueConstraint(
            "budget_id",
            "category_id",
            name="uq_categories_budget_category_id",
        ),
        CheckConstraint(
            "limit_amount > 0",
            name="ck_categories_limit_positive",
        ),
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_categories_name_not_empty",
        ),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
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

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    limit_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    budget: Mapped["Budget"] = relationship(
        back_populates="categories",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )

    @property
    def currency(self) -> str:
        """Return the currency inherited from the owning budget."""
        return self.budget.currency