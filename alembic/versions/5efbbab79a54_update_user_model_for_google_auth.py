"""update user model for google auth

Revision ID: 5efbbab79a54
Revises: g2c5d8e4f7b1
Create Date: 2026-08-03 22:30:17.786808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5efbbab79a54"
down_revision: Union[str, Sequence[str], None] = "g2c5d8e4f7b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make username nullable
    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=50),
        nullable=True,
    )

    # Make hashed_password nullable
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    # Add google_id
    op.add_column(
        "users",
        sa.Column("google_id", sa.String(length=255), nullable=True),
    )

    # Create unique index for google_id
    op.create_index(
        "ix_users_google_id",
        "users",
        ["google_id"],
        unique=True,
    )


def downgrade() -> None:
    # Drop index and column
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")

    # Restore NOT NULL constraints
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.alter_column(
        "users",
        "username",
        existing_type=sa.String(length=50),
        nullable=False,
    )