"""align user account fields with the User Service data model

Revision ID: 9a1f2c3d4e5f
Revises: f6c8ebe9976c
Create Date: 2026-10-31 15:25:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a1f2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f6c8ebe9976c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.drop_constraint(
        "user_accounts_google_user_id_key",
        "user_accounts",
        type_="unique",
    )
    op.drop_column("user_accounts", "google_user_id")
    op.alter_column(
        "user_accounts",
        "email",
        existing_type=sa.String(length=254),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "user_accounts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )


def downgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column("google_user_id", sa.String(length=255), nullable=True),
    )
    op.alter_column(
        "user_accounts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.drop_column("user_accounts", "password_hash")
    op.alter_column(
        "user_accounts",
        "email",
        existing_type=sa.String(length=255),
        type_=sa.String(length=254),
        existing_nullable=False,
    )
    op.create_unique_constraint(
        "user_accounts_google_user_id_key",
        "user_accounts",
        ["google_user_id"],
    )
