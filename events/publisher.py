"""
EventPublisher — the single point through which all application events flow.

Current implementation: synchronous PostgreSQL write.

To migrate to Redis Streams / Kafka / RabbitMQ in the future:
  1. Replace the body of PostgresEventPublisher.publish()
     (or introduce a new class, e.g. RedisEventPublisher).
  2. Change the factory function `get_publisher()` to return the new backend.
  3. No other application code needs to change — callers depend only on
     the `publish_event()` interface, not the concrete implementation.

Usage anywhere in the app:
    from events.publisher import publish_event
    from events.enums import EventType, EntityType

    publish_event(
        db,
        event_type=EventType.USER_LOGIN,
        user_id=user.id,
        metadata={"ip": request.client.host},
    )
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from .enums import EventType, EntityType
from .models import EventLog

if TYPE_CHECKING:
    pass


class PostgresEventPublisher:
    """
    Synchronous, PostgreSQL-backed publisher.

    Every call to `.publish()` immediately writes one row to event_logs
    within the caller's existing database session (no extra transaction).

    Future swap point:
        Replace this class body with a Redis / Kafka producer.
        Keep the same `.publish()` signature so callers are unaffected.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def publish(
        self,
        event_type: EventType,
        user_id: int | None = None,
        entity_type: EntityType | None = None,
        entity_id: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        log = EventLog(
            user_id=user_id,
            event_type=event_type.value,
            entity_type=entity_type.value if entity_type else None,
            entity_id=entity_id,
            payload=metadata or {},
        )
        self._db.add(log)
        self._db.commit()


# ── Public interface ──────────────────────────────────────────────────────────
# Callers use this function, never the class directly.
# Swapping the backend = changing only this function.

def publish_event(
    db: Session,
    event_type: EventType,
    user_id: int | None = None,
    entity_type: EntityType | None = None,
    entity_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Publish an application event. Currently writes synchronously to PostgreSQL."""
    PostgresEventPublisher(db).publish(
        event_type=event_type,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
    )
