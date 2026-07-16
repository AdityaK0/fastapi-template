from datetime import date as DateType
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from .models import Tracker, TrackerHabit, TrackerProgress, TrackerStatus


class TrackerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, tracker: Tracker) -> Tracker:
        self.db.add(tracker)
        self.db.commit()
        self.db.refresh(tracker)
        return tracker

    def get_by_id(self, tracker_id: int, user_id: int) -> Tracker | None:
        return self.db.scalar(
            select(Tracker).where(
                Tracker.id == tracker_id,
                Tracker.user_id == user_id,
                Tracker.is_active == True,
            )
        )

    def get_all(self, user_id: int, status: TrackerStatus | None = None) -> list[Tracker]:
        q = select(Tracker).where(Tracker.user_id == user_id, Tracker.is_active == True)
        if status:
            q = q.where(Tracker.status == status)
        q = q.order_by(Tracker.created_at.desc())
        return list(self.db.scalars(q).all())

    def update(self, tracker: Tracker) -> Tracker:
        self.db.commit()
        self.db.refresh(tracker)
        return tracker

    def delete(self, tracker: Tracker) -> None:
        from datetime import datetime
        tracker.is_active = False
        tracker.deleted_at = datetime.now()
        self.db.commit()

    def sync_statuses(self) -> None:
        """Auto-update tracker statuses based on today's date."""
        today = DateType.today()
        trackers = self.db.scalars(
            select(Tracker).where(Tracker.is_active == True)
        ).all()
        for t in trackers:
            if t.status == TrackerStatus.paused:
                continue
            if t.start_date > today:
                t.status = TrackerStatus.upcoming
            elif t.end_date < today:
                t.status = TrackerStatus.completed
            else:
                t.status = TrackerStatus.active
        self.db.commit()


class TrackerHabitRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_many(self, habits: list[TrackerHabit]) -> list[TrackerHabit]:
        self.db.add_all(habits)
        self.db.commit()
        for h in habits:
            self.db.refresh(h)
        return habits


class TrackerProgressRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tracker_id: int, day_index: int, habit_id: int) -> TrackerProgress | None:
        return self.db.scalar(
            select(TrackerProgress).where(
                TrackerProgress.tracker_id == tracker_id,
                TrackerProgress.day_index == day_index,
                TrackerProgress.habit_id == habit_id,
            )
        )

    def upsert(self, tracker_id: int, day_index: int, habit_id: int, completed: bool) -> TrackerProgress:
        existing = self.get(tracker_id, day_index, habit_id)
        if existing:
            existing.completed = completed
            self.db.commit()
            self.db.refresh(existing)
            return existing
        progress = TrackerProgress(
            tracker_id=tracker_id,
            day_index=day_index,
            habit_id=habit_id,
            completed=completed,
        )
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def get_all_for_tracker(self, tracker_id: int) -> list[TrackerProgress]:
        return list(
            self.db.scalars(
                select(TrackerProgress).where(TrackerProgress.tracker_id == tracker_id)
            ).all()
        )
