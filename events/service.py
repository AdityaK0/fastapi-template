"""Activity query service — reads from event_logs."""
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, select, cast, Date

from .models import EventLog
from .enums import EventType
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
            # Default: current year from Jan 1
            start_date = date(today.year, 1, 1)

        # Aggregate: one row per calendar day with event count
        rows = self._db.execute(
            select(
                cast(EventLog.created_at, Date).label("activity_date"),
                func.count(EventLog.id).label("cnt"),
            )
            .where(
                EventLog.user_id == user_id,
                EventLog.event_type == EventType.USER_LOGIN.value,
                EventLog.created_at >= datetime.combine(start_date, datetime.min.time()),
                EventLog.created_at <= datetime.combine(end_date, datetime.max.time()),
            )
            .group_by("activity_date")
            .order_by("activity_date")
        ).all()

        # Build a complete date range with zero-fill for missing days
        counts_by_date: dict[date, int] = {r.activity_date: r.cnt for r in rows}
        data: list[ActivityDay] = []
        current = start_date
        while current <= end_date:
            data.append(ActivityDay(date=current, count=counts_by_date.get(current, 0)))
            current += timedelta(days=1)

        return ActivityResponse(
            data=data,
            total_events=sum(r.cnt for r in rows),
            start_date=start_date,
            end_date=end_date,
        )
