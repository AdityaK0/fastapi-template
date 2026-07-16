"""add profile fields to users

Revision ID: c3d7e1f2b8a4
Revises: b5f2a9e7d3c1
Create Date: 2026-07-16 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d7e1f2b8a4'
down_revision = 'b5f2a9e7d3c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS website VARCHAR(200)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(100)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_path VARCHAR(500)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP")


def downgrade() -> None:
    for col in ['first_name', 'last_name', 'display_name', 'bio', 'website', 'location', 'avatar_path', 'last_login']:
        op.execute(f"ALTER TABLE users DROP COLUMN IF EXISTS {col}")
