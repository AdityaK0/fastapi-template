"""add daily_presence read model

Revision ID: f1b4e8c9d2a3
Revises: e9a3c2f1d7b6
Create Date: 2026-07-17 10:00:00.000000

Why daily_presence instead of querying event_logs directly?
  The activity heatmap is a read-heavy operation run on every dashboard load.
  event_logs is an append-only log that will grow unbounded.
  daily_presence is a compact projection (one row per user per day) that
  stays small and fast regardless of event volume.
"""
from alembic import op

revision = 'f1b4e8c9d2a3'
down_revision = 'e9a3c2f1d7b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_presence (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            activity_date DATE NOT NULL,
            last_seen_at  TIMESTAMP NOT NULL,
            event_count   INTEGER NOT NULL DEFAULT 1,
            CONSTRAINT uq_user_activity_date UNIQUE (user_id, activity_date)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_presence_user_id ON daily_presence(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_presence_date    ON daily_presence(activity_date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS daily_presence")
