"""Activity query service — reads from daily_presence (the read model)."""
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import DailyPresence
from .schema import ActivityDay, ActivityResponse


class ActivityService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_activity(
        self,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ActivityResponse:
        today = date.today()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = date(today.year, 1, 1)

        rows = self._db.scalars(
            select(DailyPresence).where(
                DailyPresence.user_id == user_id,
                DailyPresence.activity_date >= start_date,
                DailyPresence.activity_date <= end_date,
            )
        ).all()

        counts: dict[date, int] = {r.activity_date: r.event_count for r in rows}

        data: list[ActivityDay] = []
        current = start_date
        while current <= end_date:
            data.append(ActivityDay(date=current, count=counts.get(current, 0)))
            current += timedelta(days=1)

        return ActivityResponse(
            data=data,
            total_events=sum(r.event_count for r in rows),
            start_date=start_date,
            end_date=end_date,
        )
