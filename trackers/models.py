from datetime import date as DateType
from sqlalchemy import String, Text, Integer, ForeignKey, Boolean, Date, Enum as SAEnum
from sqlalchemy.orm import mapped_column, Mapped, relationship
from utils.models import BaseModel
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
