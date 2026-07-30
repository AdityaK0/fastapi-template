"""
Persistence models for the event system.

EventLog       — append-only immutable event history (the write model).
DailyPresence  — one row per user per day (the read model / projection).

Design constraints for EventLog:
  - No updated_at, no is_active, no soft-delete.
  - user_id ON DELETE SET NULL so events outlive users.
  - "metadata" stored as JSONB, mapped to "payload" (SQLAlchemy reserves "metadata").

Design constraints for DailyPresence:
  - One row per (user_id, activity_date) — enforced by UNIQUE constraint.
  - Always updated via UPSERT, never a plain INSERT.
  - The dashboard heatmap reads from this table, never from event_logs directly.
"""
from datetime import datetime, date as DateType
from sqlalchemy import Integer, String, ForeignKey, DateTime, Date, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class EventLog(Base):
    """Append-only event history. Never updated or deleted."""
    __tablename__ = "event_logs"

    id:          Mapped[int]        = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type:  Mapped[str]        = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload:     Mapped[dict]       = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at:  Mapped[datetime]   = mapped_column(DateTime, default=datetime.now, nullable=False)


class DailyPresence(Base):
    """
    Read model / projection updated by the update_presence subscriber.

    One row per user per calendar day.  Upserted — never plain-inserted.
    The activity heatmap API queries this table instead of event_logs
    so the dashboard remains fast as event volume grows.
    """
    __tablename__ = "daily_presence"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_user_activity_date"),
    )

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:       Mapped[int]      = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    last_seen_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_count:   Mapped[int]      = mapped_column(Integer, nullable=False, default=1)
