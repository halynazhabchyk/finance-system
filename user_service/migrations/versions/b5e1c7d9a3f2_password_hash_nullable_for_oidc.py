"""password_hash is optional: profiles are provisioned from Keycloak tokens (ЛР №5)

Credentials now live in Keycloak; a profile created at the first sign-in has no
local password. The column is kept (not dropped) so earlier rows stay intact.

Revision ID: b5e1c7d9a3f2
Revises: 9a1f2c3d4e5f
Create Date: 2026-11-14 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5e1c7d9a3f2"
down_revision: Union[str, Sequence[str], None] = "9a1f2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_accounts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    # Profiles without a password would violate NOT NULL; they must be removed first.
    op.execute("DELETE FROM user_accounts WHERE password_hash IS NULL")
    op.alter_column(
        "user_accounts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )
