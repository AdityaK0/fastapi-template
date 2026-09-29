"""
TrackerAnalyticsService — read-only breakdowns of one tracker's progress.

Headline numbers (completion %, streaks, elapsed days) are taken from
TrackerService.get_detail so they always match the tracker page. This module
adds what the page doesn't compute: per-day, per-habit and per-week views and
streak runs. Everything is loaded through get_detail, so the same ownership
filter as the REST API applies: a tracker that isn't the user's raises 404.

All outputs are plain JSON-ready dicts with 1-based day numbers and ISO dates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .schema import TrackerDetail
from .service import TrackerService

DEFAULT_RECENT_DAYS = 14
MAX_RANGE_DAYS = 62


@dataclass(frozen=True)
class DayRecord:
    index: int              # 0-based day index
    date: date
    done: frozenset[int]    # habit ids checked on this day
    is_today: bool


class TrackerAnalytics:
    """Derived views over a loaded tracker. Build it with TrackerAnalyticsService.load()."""

    def __init__(self, detail: TrackerDetail, today: date):
        self.detail = detail
        self.today = today
        self.habits = [(h.id, h.name) for h in sorted(detail.habits, key=lambda h: h.position)]
        habit_ids = {habit_id for habit_id, _ in self.habits}

        done_by_day: dict[int, set[int]] = {}
        for p in detail.progress:
            if p.completed and p.habit_id in habit_ids:
                done_by_day.setdefault(p.day_index, set()).add(p.habit_id)

        self.days = [
            DayRecord(
                index=i,
                date=detail.start_date + timedelta(days=i),
                done=frozenset(done_by_day.get(i, ())),
                is_today=detail.start_date + timedelta(days=i) == today,
            )
            for i in range(detail.days_elapsed)
        ]
        # Today is still in progress, so rates and streak runs use finished days only.
        self.finished = [d for d in self.days if not d.is_today]
        self.notes: dict[int, str] = {}
        for key, text in (detail.day_notes or {}).items():
            if str(key).isdigit() and int(key) < detail.duration_days and text and text.strip():
                self.notes[int(key)] = text.strip()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _names(self, ids) -> list[str]:
        return [name for habit_id, name in self.habits if habit_id in ids]

    def _missed(self, day: DayRecord) -> list[str]:
        return [name for habit_id, name in self.habits if habit_id not in day.done]

    def _complete(self, day: DayRecord) -> bool:
        return bool(self.habits) and len(day.done) == len(self.habits)

    def _percent(self, done: int, total: int) -> float:
        return round(done / total * 100, 1) if total else 0.0

    def _today_record(self) -> DayRecord | None:
        return next((d for d in self.days if d.is_today), None)

    def _clamp_range(self, start_day: int | None, end_day: int | None, default_days: int) -> tuple[int, int, bool]:
        """Resolve 1-based inclusive day numbers to 0-based indexes within elapsed days."""
        last = len(self.days) - 1
        if last < 0:
            return 0, -1, False
        end = last if end_day is None else min(max(end_day - 1, 0), last)
        start = max(end - default_days + 1, 0) if start_day is None else min(max(start_day - 1, 0), last)
        if start > end:
            start, end = end, start
        truncated = end - start + 1 > MAX_RANGE_DAYS
        if truncated:
            start = end - MAX_RANGE_DAYS + 1
        return start, end, truncated

    def _streak_through_yesterday(self) -> int:
        streak = 0
        for day in reversed(self.finished):
            if not self._complete(day):
                break
            streak += 1
        return streak

    # ── views ────────────────────────────────────────────────────────────────

    def overview(self) -> dict:
        d = self.detail
        today = self._today_record()
        return {
            "tracker": {
                "name": d.name,
                "description": d.description,
                "status": d.status.value,
                "start_date": d.start_date.isoformat(),
                "end_date": d.end_date.isoformat(),
                "duration_days": d.duration_days,
                "habits": [{"habit_id": habit_id, "name": name} for habit_id, name in self.habits],
            },
            "today": {
                "date": self.today.isoformat(),
                "day": today.index + 1 if today else None,
                "done": self._names(today.done) if today else [],
                "not_done_yet": self._missed(today) if today else [],
            },
            "progress": {
                "days_elapsed": d.days_elapsed,
                "days_remaining": d.days_remaining,
                "completion_percent": d.completion_percent,
                "completed_checkins": d.completed_habits,
                "missed_checkins": d.missed_habits,
                "complete_days": sum(1 for day in self.days if self._complete(day)),
                "current_streak": d.current_streak,
                "streak_through_yesterday": self._streak_through_yesterday(),
                "longest_streak": d.longest_streak,
                "days_with_notes": len(self.notes),
            },
        }

    def daily(self, start_day: int | None = None, end_day: int | None = None) -> dict:
        start, end, truncated = self._clamp_range(start_day, end_day, DEFAULT_RECENT_DAYS)
        days = [
            {
                "day": day.index + 1,
                "date": day.date.isoformat(),
                "done": self._names(day.done),
                "missed": self._missed(day),
                "completion_percent": self._percent(len(day.done), len(self.habits)),
                "all_done": self._complete(day),
                "has_note": day.index in self.notes,
                "in_progress": day.is_today,
            }
            for day in self.days[start:end + 1]
        ]
        return {"days": days, "truncated_to_last_days": MAX_RANGE_DAYS if truncated else None}

    def habit_stats(self, last_n_days: int | None = None) -> dict:
        window = self.finished[-last_n_days:] if last_n_days else self.finished
        today = self._today_record()
        habits = []
        for habit_id, name in self.habits:
            done_days = [d for d in window if habit_id in d.done]
            longest = run = 0
            for day in window:
                run = run + 1 if habit_id in day.done else 0
                longest = max(longest, run)
            current = 0
            for day in reversed(window):
                if habit_id not in day.done:
                    break
                current += 1
            missed = [d for d in window if habit_id not in d.done]
            habits.append({
                "habit_id": habit_id,
                "name": name,
                "done_days": len(done_days),
                "finished_days": len(window),
                "completion_rate": self._percent(len(done_days), len(window)),
                "current_run": current,
                "longest_run": longest,
                "last_done": done_days[-1].date.isoformat() if done_days else None,
                "last_missed": missed[-1].date.isoformat() if missed else None,
                "done_today": habit_id in today.done if today else None,
            })
        return {"window_days": len(window), "habits": habits}

    def weekly(self) -> dict:
        weeks = []
        for start in range(0, len(self.finished), 7):
            chunk = self.finished[start:start + 7]
            done = sum(len(day.done) for day in chunk)
            weeks.append({
                "week": start // 7 + 1,
                "start_date": chunk[0].date.isoformat(),
                "end_date": chunk[-1].date.isoformat(),
                "days_counted": len(chunk),
                "completion_percent": self._percent(done, len(chunk) * len(self.habits)),
                "complete_days": sum(1 for day in chunk if self._complete(day)),
            })
        return {"weeks": weeks}

    def streaks(self, limit: int = 10) -> dict:
        runs, breaks = [], []
        run_start = None
        for i, day in enumerate(self.finished):
            if self._complete(day):
                if run_start is None:
                    run_start = i
                continue
            if run_start is not None:
                first, last = self.finished[run_start], self.finished[i - 1]
                runs.append({
                    "start_day": first.index + 1, "end_day": last.index + 1,
                    "start_date": first.date.isoformat(), "end_date": last.date.isoformat(),
                    "length": i - run_start,
                })
                breaks.append({
                    "day": day.index + 1, "date": day.date.isoformat(),
                    "missed": self._missed(day), "has_note": day.index in self.notes,
                })
                run_start = None
        if run_start is not None:
            first, last = self.finished[run_start], self.finished[-1]
            runs.append({
                "start_day": first.index + 1, "end_day": last.index + 1,
                "start_date": first.date.isoformat(), "end_date": last.date.isoformat(),
                "length": len(self.finished) - run_start, "ongoing": True,
            })
        return {
            "current_streak": self.detail.current_streak,
            "streak_through_yesterday": self._streak_through_yesterday(),
            "longest_streak": self.detail.longest_streak,
            "runs": runs[-limit:],
            "breaks": breaks[-limit:],
        }

    def note_entries(self) -> list[tuple[int, date, str]]:
        """Every day note as (0-based day index, date, text), oldest first."""
        return [
            (index, self.detail.start_date + timedelta(days=index), text)
            for index, text in sorted(self.notes.items())
        ]


class TrackerAnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def load(self, tracker_id: int, user_id: int) -> TrackerAnalytics:
        # get_detail enforces ownership and raises TRACKER_NOT_FOUND otherwise.
        detail = TrackerService(self.db).get_detail(tracker_id, user_id)
        return TrackerAnalytics(detail, today=date.today())
