"""extend processed_events into a transactional inbox

Revision ID: e9a1b3c5d7f2
Revises: d6e8f1a3b5c7
Create Date: 2026-11-07 10:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9a1b3c5d7f2"
down_revision: Union[str, Sequence[str], None] = "d6e8f1a3b5c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rows written before LR3 have no stored type; it stays NULL for them.
    op.add_column(
        "processed_events",
        sa.Column("event_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "processed_events",
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "processed_events",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="PROCESSED",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_processed_events_status",
        "processed_events",
        "status IN ('PROCESSED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_processed_events_status", "processed_events", type_="check")
    op.drop_column("processed_events", "status")
    op.drop_column("processed_events", "received_at")
    op.drop_column("processed_events", "event_type")
