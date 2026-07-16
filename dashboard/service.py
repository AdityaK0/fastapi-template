from datetime import date as DateType
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from notes.models import Note
from trackers.models import Tracker, TrackerProgress, TrackerStatus
from .schema import DashboardStats


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_stats(self, user_id: int) -> DashboardStats:
        total_trackers = self.db.scalar(
            select(func.count(Tracker.id)).where(Tracker.user_id == user_id, Tracker.is_active == True)
        ) or 0
        active = self.db.scalar(
            select(func.count(Tracker.id)).where(
                Tracker.user_id == user_id, Tracker.is_active == True, Tracker.status == TrackerStatus.active
            )
        ) or 0
        completed = self.db.scalar(
            select(func.count(Tracker.id)).where(
                Tracker.user_id == user_id, Tracker.is_active == True, Tracker.status == TrackerStatus.completed
            )
        ) or 0
        upcoming = self.db.scalar(
            select(func.count(Tracker.id)).where(
                Tracker.user_id == user_id, Tracker.is_active == True, Tracker.status == TrackerStatus.upcoming
            )
        ) or 0
        total_notes = self.db.scalar(
            select(func.count(Note.id)).where(Note.user_id == user_id, Note.is_active == True, Note.is_archived == False)
        ) or 0
        pinned_notes = self.db.scalar(
            select(func.count(Note.id)).where(
                Note.user_id == user_id, Note.is_active == True, Note.is_pinned == True
            )
        ) or 0

        # today completion across all active trackers
        today = DateType.today()
        active_trackers = self.db.scalars(
            select(Tracker).where(Tracker.user_id == user_id, Tracker.is_active == True, Tracker.status == TrackerStatus.active)
        ).all()
        today_cells = 0
        today_done = 0
        for t in active_trackers:
            day_idx = (today - t.start_date).days
            if 0 <= day_idx < t.duration_days:
                habit_count = len(t.habits)
                today_cells += habit_count
                done = self.db.scalar(
                    select(func.count(TrackerProgress.id)).where(
                        TrackerProgress.tracker_id == t.id,
                        TrackerProgress.day_index == day_idx,
                        TrackerProgress.completed == True,
                    )
                ) or 0
                today_done += done

        today_pct = round((today_done / today_cells * 100) if today_cells > 0 else 0, 1)

        return DashboardStats(
            total_trackers=total_trackers,
            active_trackers=active,
            completed_trackers=completed,
            upcoming_trackers=upcoming,
            total_notes=total_notes,
            pinned_notes=pinned_notes,
            today_completion_percent=today_pct,
        )
