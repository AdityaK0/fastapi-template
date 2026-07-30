"""
EventLogSubscriber — appends every domain event to the immutable event_log table.

critical = True: if the event log write fails, the exception propagates.
The log is the system's source of truth for what happened — losing events
silently is worse than a visible error.

This subscriber handles *all* event types because every event should be logged.
Register it for every event in registry.py.
"""
import logging

from sqlalchemy.orm import Session

from events.base import DomainEvent
from events.models import EventLog
from .base import Subscriber

logger = logging.getLogger(__name__)


class EventLogSubscriber(Subscriber):
    """Persist every domain event to the append-only event_log table."""

    critical = True

    def __init__(self, db: Session | None = None) -> None:
        super().__init__(db)

    def __call__(self, event: DomainEvent) -> None:
        if self.db is None:
            logger.warning("EventLogSubscriber: no db session, skipping")
            return

        entry = EventLog(
            user_id=getattr(event, "user_id", None),
            event_type=event.event_type,
            payload=event.model_dump(exclude={"event_id", "occurred_at"}),
        )
        self.db.add(entry)
        self.db.commit()
        logger.debug("EventLog: persisted %s id=%s", event.event_type, event.event_id)
