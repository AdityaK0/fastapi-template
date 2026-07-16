"""add tracker pinning and deleted_at timestamps

Revision ID: d4e8f1a2b9c5
Revises: c3d7e1f2b8a4
Create Date: 2026-07-16 12:00:00.000000
"""
from alembic import op

revision = 'd4e8f1a2b9c5'
down_revision = 'c3d7e1f2b8a4'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("ALTER TABLE trackers ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE notes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
    op.execute("ALTER TABLE trackers ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")

def downgrade() -> None:
    op.execute("ALTER TABLE trackers DROP COLUMN IF EXISTS is_pinned")
    op.execute("ALTER TABLE notes DROP COLUMN IF EXISTS deleted_at")
    op.execute("ALTER TABLE trackers DROP COLUMN IF EXISTS deleted_at")
