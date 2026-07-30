"""add tracker_history snapshot table

Revision ID: g2c5d8e4f7b1
Revises: f1b4e8c9d2a3
Create Date: 2026-07-17 12:00:00.000000

Design:
  One row per tracker (UNIQUE on tracker_id).
  The entire immutable history lives in a single JSONB column.
  Reading history = one indexed lookup, no per-day joins.
  This is a snapshot, not a cache — once a day is archived it is never rewritten.
"""
from alembic import op

revision = 'g2c5d8e4f7b1'
down_revision = 'f1b4e8c9d2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_history (
            id           SERIAL PRIMARY KEY,
            tracker_id   INTEGER NOT NULL UNIQUE REFERENCES trackers(id) ON DELETE CASCADE,
            snapshot     JSONB NOT NULL DEFAULT '{}',
            created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tracker_history_tracker_id ON tracker_history(tracker_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tracker_history")
