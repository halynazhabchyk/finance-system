"""create saga instances and expense saga status

Revision ID: c8e0a2b4d6f8
Revises: a3c5e7f9b1d2
Create Date: 2026-11-07 11:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8e0a2b4d6f8"
down_revision: Union[str, Sequence[str], None] = "a3c5e7f9b1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Expenses created before LR3 have no distributed operation in flight,
    # so they are treated as already confirmed.
    op.add_column(
        "expenses",
        sa.Column(
            "saga_status",
            sa.String(length=20),
            server_default="CONFIRMED",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_expenses_saga_status",
        "expenses",
        "saga_status IN ('PENDING', 'CONFIRMED', 'CANCELLED')",
    )

    op.create_table(
        "saga_instances",
        sa.Column("saga_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("saga_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_step", sa.String(length=50), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=20), nullable=True),
        sa.Column("failure_details", sa.Text(), nullable=True),
        sa.Column(
            "compensation_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("saga_id"),
        sa.UniqueConstraint(
            "saga_type",
            "aggregate_id",
            name="uq_saga_instances_type_aggregate",
        ),
        sa.CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'COMPENSATING', 'CANCELLED')",
            name="ck_saga_instances_status",
        ),
        sa.CheckConstraint(
            "failure_reason IS NULL OR failure_reason IN ('DLQ', 'TIMEOUT')",
            name="ck_saga_instances_failure_reason",
        ),
    )
    op.create_index(
        "ix_saga_instances_status_deadline",
        "saga_instances",
        ["status", "deadline_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_saga_instances_status_deadline", table_name="saga_instances")
    op.drop_table("saga_instances")
    op.drop_constraint("ck_expenses_saga_status", "expenses", type_="check")
    op.drop_column("expenses", "saga_status")
