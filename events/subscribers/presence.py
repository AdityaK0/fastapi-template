"""
PresenceProjectionSubscriber — maintains the daily_presence read model.

This subscriber listens only to UserPresent events and upserts one row per
user per calendar day.  The activity heatmap queries daily_presence —
never event_logs directly — so the dashboard stays fast as event volume grows.

critical = False: a failed presence upsert must never crash the login flow.
The event is still logged by EventLogSubscriber, so data is not lost.

Architecture note:
    The subscriber owns orchestration (when to upsert, with what values).
    The repository owns persistence (how to upsert).
    This separation makes both independently testable.
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from events.base import DomainEvent
from events.domain_events import UserPresent
from .base import Subscriber

logger = logging.getLogger(__name__)


class PresenceRepository:
    """
    Thin persistence layer for daily_presence.
    Injected into the subscriber — swap for a mock in tests.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert(self, user_id: int, activity_date, last_seen_at: datetime) -> None:
        from sqlalchemy import text
        self._db.execute(
            text("""
                INSERT INTO daily_presence (user_id, activity_date, last_seen_at, event_count)
                VALUES (:user_id, :date, :seen_at, 1)
                ON CONFLICT (user_id, activity_date)
                DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    event_count  = daily_presence.event_count + 1
            """),
            {"user_id": user_id, "date": activity_date, "seen_at": last_seen_at},
        )
        self._db.commit()


class PresenceProjectionSubscriber(Subscriber):
    """Update the daily_presence projection on every UserPresent event."""

    critical = False

    def __init__(self, db: Session | None = None) -> None:
        super().__init__(db)
        self._repo = PresenceRepository(db) if db is not None else None

    def __call__(self, event: DomainEvent) -> None:
        if not isinstance(event, UserPresent):
            return
        if self._repo is None:
            logger.warning("PresenceProjectionSubscriber: no db session, skipping")
            return

        self._repo.upsert(
            user_id=event.user_id,
            activity_date=event.occurred_at.date(),
            last_seen_at=event.occurred_at,
        )
        logger.debug(
            "DailyPresence: upserted user_id=%s date=%s",
            event.user_id, event.occurred_at.date(),
        )
