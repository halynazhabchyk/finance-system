"""add retry diagnostics and saga link to outbox events

Revision ID: a3c5e7f9b1d2
Revises: f1a2b3c4d5e6
Create Date: 2026-11-07 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3c5e7f9b1d2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column(
            "publish_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "outbox_events",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("saga_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_outbox_events_saga_id", "outbox_events", ["saga_id"])


def downgrade() -> None:
    op.drop_index("ix_outbox_events_saga_id", table_name="outbox_events")
    op.drop_column("outbox_events", "saga_id")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "publish_attempts")
