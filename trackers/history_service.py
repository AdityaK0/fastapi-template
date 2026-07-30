"""
TrackerHistoryService — owns all immutable snapshot logic.

Responsibilities:
    validate_day_is_mutable  — 409 if caller requests a past day
    archive_completed_days   — snapshot any unarchived past days
    get_snapshot             — read the snapshot for a tracker

Design decisions:
    - Synchronous: archiving happens inside the same request that modifies progress.
    - One snapshot row per tracker (UPSERT pattern).
    - Days are identified by their 0-based index (str key in JSON for JSONB portability).
    - Habit names (not IDs) used as keys — human-readable, survives habit reordering.
    - Snapshot is versioned (version=1) so future schema changes are detectable.
    - SQLAlchemy doesn't auto-detect JSONB dict mutations; we reassign the full dict.

Future extension point:
    After archiving, publish a TrackerDayArchived(tracker_id, day_index) domain event
    here so downstream consumers (analytics, XP, achievements) react without
    touching this service or the API layer.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

from utils.exceptions import AppException
from .models import Tracker, TrackerHistory

SNAPSHOT_VERSION = 1


class TrackerHistoryService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def validate_day_is_mutable(self, tracker: Tracker, day_index: int) -> None:
        """
        Raise 409 if day_index refers to a past (already archived) day.

        The current tracker day is mutable; everything before it is not.
        This check must run on the backend — frontend validation alone is insufficient.
        """
        current = self._current_day_index(tracker)
        if day_index < current:
            raise AppException(
                "Past tracker days are immutable",
                status_code=409,
                error_code="DAY_IMMUTABLE",
            )

    def archive_completed_days(self, tracker: Tracker) -> dict:
        """
        Snapshot every past day that hasn't been archived yet.

        Called on every progress update so the snapshot stays current.
        Idempotent — re-archiving an already-archived day is a no-op.

        Returns the updated snapshot dict.
        """
        current = self._current_day_index(tracker)
        if current == 0:
            return self._get_snapshot(tracker.id)

        history = self._get_or_create(tracker.id)
        snapshot = dict(history.snapshot) if history.snapshot else self._empty_snapshot(tracker.id)

        last_archived: int = snapshot.get("last_archived_day", -1)
        days_to_archive = range(last_archived + 1, current)

        if not days_to_archive:
            return snapshot  # nothing new to archive

        habit_map = {h.id: h.name for h in tracker.habits}
        progress_by_day: dict[int, list] = {}
        for p in tracker.progress:
            progress_by_day.setdefault(p.day_index, []).append(p)

        days_dict = dict(snapshot.get("days", {}))
        now_str = datetime.now().isoformat()

        for day_idx in days_to_archive:
            day_progress = progress_by_day.get(day_idx, [])
            completed_ids = {p.habit_id for p in day_progress if p.completed}
            habits_snapshot = {habit_map[h.id]: (h.id in completed_ids) for h in tracker.habits}

            completed_count = len(completed_ids)
            missed_count = len(tracker.habits) - completed_count
            completion_pct = round(
                (completed_count / len(tracker.habits) * 100) if tracker.habits else 0, 1
            )
            day_date = (tracker.start_date + timedelta(days=day_idx)).isoformat()

            days_dict[str(day_idx)] = {
                "date": day_date,
                "completion": completion_pct,
                "completed": completed_count,
                "missed": missed_count,
                "habits": habits_snapshot,
                "snapshot_created_at": now_str,
                "last_updated_at": now_str,
            }

        snapshot["days"] = days_dict
        snapshot["last_archived_day"] = current - 1
        snapshot["last_snapshot_at"] = now_str

        # Reassign full dict — SQLAlchemy doesn't detect JSONB in-place mutations
        history.snapshot = snapshot
        history.updated_at = datetime.now()
        self._db.commit()

        return snapshot

    def get_snapshot(self, tracker_id: int) -> dict:
        return self._get_snapshot(tracker_id)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _current_day_index(self, tracker: Tracker) -> int:
        """0-based index of today within the tracker (clamped to valid range)."""
        elapsed = (date.today() - tracker.start_date).days
        return max(0, min(elapsed, tracker.duration_days - 1))

    def _get_snapshot(self, tracker_id: int) -> dict:
        history = self._db.scalar(
            select(TrackerHistory).where(TrackerHistory.tracker_id == tracker_id)
        )
        return history.snapshot if history else {}

    def _get_or_create(self, tracker_id: int) -> TrackerHistory:
        history = self._db.scalar(
            select(TrackerHistory).where(TrackerHistory.tracker_id == tracker_id)
        )
        if history is None:
            history = TrackerHistory(
                tracker_id=tracker_id,
                snapshot=self._empty_snapshot(tracker_id),
            )
            self._db.add(history)
            self._db.flush()
        return history

    def _empty_snapshot(self, tracker_id: int) -> dict:
        return {
            "version": SNAPSHOT_VERSION,
            "tracker_id": tracker_id,
            "last_archived_day": -1,
            "last_snapshot_at": None,
            "days": {},
        }
