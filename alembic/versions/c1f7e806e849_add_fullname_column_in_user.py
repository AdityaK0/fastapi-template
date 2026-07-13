"""add fullname column in user

Revision ID: c1f7e806e849
Revises: c096e47110e9
Create Date: 2026-07-13 16:00:29.237759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f7e806e849'
down_revision: Union[str, Sequence[str], None] = 'c096e47110e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('fullname', sa.String(length=200), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'fullname')
