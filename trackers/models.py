from datetime import date as DateType, datetime
from sqlalchemy import String, Text, Integer, ForeignKey, Boolean, Date, DateTime, Enum as SAEnum, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship
from utils.models import BaseModel
from database import Base
import enum


class TrackerStatus(str, enum.Enum):
    upcoming = "upcoming"
    active = "active"
    completed = "completed"
    paused = "paused"


class Tracker(BaseModel):
    __tablename__ = "trackers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    end_date: Mapped[DateType] = mapped_column(Date, nullable=False)
    status: Mapped[TrackerStatus] = mapped_column(
        SAEnum(TrackerStatus, name="trackerstatus"),
        default=TrackerStatus.upcoming,
        nullable=False,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    habits: Mapped[list["TrackerHabit"]] = relationship(
        back_populates="tracker", cascade="all, delete", order_by="TrackerHabit.position"
    )
    progress: Mapped[list["TrackerProgress"]] = relationship(
        back_populates="tracker", cascade="all, delete"
    )


class TrackerHabit(BaseModel):
    __tablename__ = "tracker_habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tracker: Mapped["Tracker"] = relationship(back_populates="habits")
    progress: Mapped[list["TrackerProgress"]] = relationship(
        back_populates="habit", cascade="all, delete"
    )


class TrackerProgress(BaseModel):
    __tablename__ = "tracker_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("trackers.id", ondelete="CASCADE"), nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    habit_id: Mapped[int] = mapped_column(ForeignKey("tracker_habits.id", ondelete="CASCADE"), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tracker: Mapped["Tracker"] = relationship(back_populates="progress")
    habit: Mapped["TrackerHabit"] = relationship(back_populates="progress")


class TrackerHistory(Base):
    """
    Immutable snapshot of all archived tracker days.

    One row per tracker (UNIQUE on tracker_id).
    The `snapshot` JSONB column holds the complete day-by-day history.
    This is NOT a cache — once a day is written here it is never rewritten.

    Snapshot schema (version 1):
    {
        "version": 1,
        "tracker_id": 15,
        "last_archived_day": 4,
        "last_snapshot_at": "2026-07-25T00:00:00",
        "days": {
            "0": {
                "date": "2026-07-21",
                "completion": 100.0,
                "completed": 2,
                "missed": 0,
                "habits": {"Morning": true, "Night": true},
                "snapshot_created_at": "2026-07-22T00:00:00",
                "last_updated_at": "2026-07-22T00:00:00"
            }
        }
    }
    """
    __tablename__ = "tracker_history"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True)
    tracker_id: Mapped[int]  = mapped_column(
        ForeignKey("trackers.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    snapshot:   Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
