"""add notes and trackers

Revision ID: b5f2a9e7d3c1
Revises: a3f9b2d1c4e8
Create Date: 2026-07-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b5f2a9e7d3c1'
down_revision = 'a3f9b2d1c4e8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title       VARCHAR(500) NOT NULL,
            content     TEXT,
            is_pinned   BOOLEAN NOT NULL DEFAULT false,
            is_archived BOOLEAN NOT NULL DEFAULT false,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            is_active   BOOLEAN NOT NULL DEFAULT true
        )
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE trackerstatus AS ENUM ('upcoming', 'active', 'completed', 'paused');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS trackers (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name          VARCHAR(200) NOT NULL,
            description   TEXT,
            duration_days INTEGER NOT NULL,
            start_date    DATE NOT NULL,
            end_date      DATE NOT NULL,
            status        trackerstatus NOT NULL DEFAULT 'upcoming',
            created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            is_active     BOOLEAN NOT NULL DEFAULT true
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_habits (
            id         SERIAL PRIMARY KEY,
            tracker_id INTEGER NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            name       VARCHAR(200) NOT NULL,
            position   INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            is_active  BOOLEAN NOT NULL DEFAULT true
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tracker_progress (
            id         SERIAL PRIMARY KEY,
            tracker_id INTEGER NOT NULL REFERENCES trackers(id) ON DELETE CASCADE,
            day_index  INTEGER NOT NULL,
            habit_id   INTEGER NOT NULL REFERENCES tracker_habits(id) ON DELETE CASCADE,
            completed  BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            is_active  BOOLEAN NOT NULL DEFAULT true,
            CONSTRAINT uq_tracker_day_habit UNIQUE (tracker_id, day_index, habit_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tracker_progress")
    op.execute("DROP TABLE IF EXISTS tracker_habits")
    op.execute("DROP TABLE IF EXISTS trackers")
    op.execute("DROP TABLE IF EXISTS notes")
    op.execute("DROP TYPE IF EXISTS trackerstatus")
