from datetime import date as DateType, timedelta
from sqlalchemy.orm import Session

from .models import Tracker, TrackerHabit, TrackerProgress, TrackerStatus
from .repository import TrackerRepository, TrackerHabitRepository, TrackerProgressRepository
from .schema import TrackerDetail, TrackerSummary, ProgressResponse, HabitResponse
from utils.exceptions import AppException


def _compute_streak(progress_list: list[TrackerProgress], habit_ids: list[int], days_elapsed: int):
    """Returns (current_streak, longest_streak)."""
    if not habit_ids or days_elapsed == 0:
        return 0, 0

    def day_complete(day_idx: int) -> bool:
        day_progress = [p for p in progress_list if p.day_index == day_idx]
        completed_habits = {p.habit_id for p in day_progress if p.completed}
        return all(h in completed_habits for h in habit_ids)

    current_streak = 0
    longest_streak = 0
    streak = 0
    for d in range(days_elapsed):
        if day_complete(d):
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0

    # current streak = streak from today backwards
    current_streak = 0
    for d in range(days_elapsed - 1, -1, -1):
        if day_complete(d):
            current_streak += 1
        else:
            break

    return current_streak, longest_streak


class TrackerService:
    def __init__(self, db: Session):
        self.repo = TrackerRepository(db)
        self.habit_repo = TrackerHabitRepository(db)
        self.progress_repo = TrackerProgressRepository(db)

    def create(self, user_id: int, data) -> Tracker:
        start = data.start_date
        end = start + timedelta(days=data.duration_days - 1)
        today = DateType.today()
        if start > today:
            status = TrackerStatus.upcoming
        elif end < today:
            status = TrackerStatus.completed
        else:
            status = TrackerStatus.active

        tracker = Tracker(
            user_id=user_id,
            name=data.name,
            description=data.description,
            duration_days=data.duration_days,
            start_date=start,
            end_date=end,
            status=status,
        )
        tracker = self.repo.create(tracker)

        habits = [
            TrackerHabit(tracker_id=tracker.id, name=h.name, position=h.position)
            for h in data.habits
        ]
        if habits:
            self.habit_repo.create_many(habits)
        # Refresh to load relationships
        self.repo.update(tracker)
        return tracker

    def list_trackers(self, user_id: int, status: TrackerStatus | None = None) -> list[TrackerSummary]:
        trackers = self.repo.get_all(user_id, status=status)
        result = []
        for t in trackers:
            summary = self._build_summary(t)
            result.append(summary)
        return result

    def get_detail(self, tracker_id: int, user_id: int) -> TrackerDetail:
        tracker = self.repo.get_by_id(tracker_id, user_id)
        if not tracker:
            raise AppException("Tracker not found", status_code=404, error_code="TRACKER_NOT_FOUND")
        return self._build_detail(tracker)

    def update(self, tracker_id: int, user_id: int, data) -> Tracker:
        tracker = self.repo.get_by_id(tracker_id, user_id)
        if not tracker:
            raise AppException("Tracker not found", status_code=404, error_code="TRACKER_NOT_FOUND")
        if data.name is not None:
            tracker.name = data.name
        if data.description is not None:
            tracker.description = data.description
        if data.status is not None:
            tracker.status = data.status
        return self.repo.update(tracker)

    def delete(self, tracker_id: int, user_id: int) -> None:
        tracker = self.repo.get_by_id(tracker_id, user_id)
        if not tracker:
            raise AppException("Tracker not found", status_code=404, error_code="TRACKER_NOT_FOUND")
        self.repo.delete(tracker)

    def update_progress(self, tracker_id: int, user_id: int, day_index: int, habit_id: int, completed: bool) -> TrackerProgress:
        tracker = self.repo.get_by_id(tracker_id, user_id)
        if not tracker:
            raise AppException("Tracker not found", status_code=404, error_code="TRACKER_NOT_FOUND")
        habit_ids = [h.id for h in tracker.habits]
        if habit_id not in habit_ids:
            raise AppException("Habit not found in this tracker", status_code=404, error_code="HABIT_NOT_FOUND")
        if day_index < 0 or day_index >= tracker.duration_days:
            raise AppException("Invalid day index", status_code=400, error_code="INVALID_DAY")
        return self.progress_repo.upsert(tracker_id, day_index, habit_id, completed)

    def _build_summary(self, tracker: Tracker) -> TrackerSummary:
        today = DateType.today()
        days_elapsed = max(0, min((today - tracker.start_date).days + 1, tracker.duration_days))
        progress_list = self.progress_repo.get_all_for_tracker(tracker.id)
        habit_ids = [h.id for h in tracker.habits]
        total_cells = days_elapsed * len(habit_ids) if habit_ids else 0
        completed_cells = sum(1 for p in progress_list if p.completed and p.day_index < days_elapsed)
        completion_percent = round((completed_cells / total_cells * 100) if total_cells > 0 else 0, 1)
        current_streak, _ = _compute_streak(progress_list, habit_ids, days_elapsed)
        return TrackerSummary(
            id=tracker.id,
            name=tracker.name,
            description=tracker.description,
            duration_days=tracker.duration_days,
            start_date=tracker.start_date,
            end_date=tracker.end_date,
            status=tracker.status,
            habit_count=len(tracker.habits),
            completion_percent=completion_percent,
            current_streak=current_streak,
            created_at=tracker.created_at,
        )

    def _build_detail(self, tracker: Tracker) -> TrackerDetail:
        today = DateType.today()
        days_elapsed = max(0, min((today - tracker.start_date).days + 1, tracker.duration_days))
        days_remaining = max(0, tracker.duration_days - days_elapsed)
        progress_list = self.progress_repo.get_all_for_tracker(tracker.id)
        habit_ids = [h.id for h in tracker.habits]
        total_cells = days_elapsed * len(habit_ids) if habit_ids else 0
        completed_cells = sum(1 for p in progress_list if p.completed and p.day_index < days_elapsed)
        missed_cells = total_cells - completed_cells
        completion_percent = round((completed_cells / total_cells * 100) if total_cells > 0 else 0, 1)
        current_streak, longest_streak = _compute_streak(progress_list, habit_ids, days_elapsed)
        return TrackerDetail(
            id=tracker.id,
            name=tracker.name,
            description=tracker.description,
            duration_days=tracker.duration_days,
            start_date=tracker.start_date,
            end_date=tracker.end_date,
            status=tracker.status,
            habits=[HabitResponse(id=h.id, name=h.name, position=h.position) for h in tracker.habits],
            progress=[ProgressResponse(day_index=p.day_index, habit_id=p.habit_id, completed=p.completed) for p in progress_list],
            completion_percent=completion_percent,
            current_streak=current_streak,
            longest_streak=longest_streak,
            completed_habits=completed_cells,
            missed_habits=missed_cells,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            created_at=tracker.created_at,
        )
