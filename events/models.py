"""
EventLog — append-only activity record.

Design constraints:
  - No updated_at: events are immutable once written.
  - No is_active / soft-delete: the log is permanent.
  - user_id is nullable so orphaned events survive user deletion.
  - metadata is a flexible JSON dict for event-specific context.
"""
from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class EventLog(Base):
    __tablename__ = "event_logs"

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id:     Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type:  Mapped[str]      = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Stored as "metadata" column in DB but mapped to "payload" to avoid
    # conflict with SQLAlchemy's reserved DeclarativeBase.metadata attribute.
    payload:     Mapped[dict]     = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
