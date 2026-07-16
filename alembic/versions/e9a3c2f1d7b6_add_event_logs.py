"""add event_logs table

Revision ID: e9a3c2f1d7b6
Revises: d4e8f1a2b9c5
Create Date: 2026-07-16 14:00:00.000000

Design note:
  - Append-only: no updated_at, no is_active, no soft-delete.
  - event_type and entity_type are stored as plain VARCHAR (Python enum values),
    NOT as PostgreSQL enums — avoids ALTER TYPE migrations when adding new event types.
  - metadata is JSONB for flexible, queryable context per event.
  - user_id is nullable (ON DELETE SET NULL) so events survive user deletion.
  - Three indexes cover the most common query patterns: by user, by type, by date range.
"""
from alembic import op

revision = 'e9a3c2f1d7b6'
down_revision = 'd4e8f1a2b9c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS event_logs (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
            event_type  VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id   INTEGER,
            metadata    JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    # Indexes for the three most common access patterns
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_user_id    ON event_logs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_event_type ON event_logs(event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_event_logs_created_at ON event_logs(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS event_logs")
