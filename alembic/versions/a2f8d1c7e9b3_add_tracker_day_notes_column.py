"""add day_notes JSONB column to trackers

Revision ID: a2f8d1c7e9b3
Revises: g2c5d8e4f7b1
Create Date: 2026-08-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2f8d1c7e9b3'
down_revision = '5efbbab79a54'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'trackers',
        sa.Column('day_notes', sa.JSON(), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('trackers', 'day_notes')
