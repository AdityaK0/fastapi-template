"""
EventBus implementations.

InMemoryEventBus — synchronous, in-process.  The default.

Migration to Redis Streams:
    1. Implement RedisStreamsEventBus(EventBus) below (or in a separate file).
    2. Call set_bus(RedisStreamsEventBus(...)) once in main.py startup.
    3. Done.  Zero changes to services, routes, domain events, or subscribers.

Critical vs non-critical subscribers:
    critical=True  — exception propagates; stops further subscriber processing.
    critical=False — exception is logged; processing continues with next subscriber.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .base import DomainEvent, EventBus
from .registry import get_subscribers

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    """
    Synchronous, in-process event bus.

    For each event:
        1. Look up subscriber classes in the registry.
        2. Instantiate each with db= (injects the current session).
        3. Call subscriber(event).
        4. If critical and it raises → propagate immediately.
        5. If non-critical and it raises → log, continue.

    Async future (per subscriber):
        Replace the subscriber call body with:
            redis.xadd("events", {"type": cls.__name__, "payload": event.model_dump_json()})
        Then a worker deserialises, instantiates, and calls the subscriber.
        The subscriber class itself needs zero changes.
    """

    def publish(self, event: DomainEvent, db: Session | None = None) -> None:
        subscriber_classes = get_subscribers(type(event))

        if not subscriber_classes:
            logger.debug("No subscribers for %s", event.event_type)
            return

        for subscriber_cls in subscriber_classes:
            subscriber = subscriber_cls(db=db)
            is_critical = getattr(subscriber, "critical", False)

            try:
                subscriber(event)
            except Exception:
                if is_critical:
                    logger.exception(
                        "Critical subscriber %s failed for %s — propagating",
                        subscriber_cls.__name__, event.event_type,
                    )
                    raise
                else:
                    logger.exception(
                        "Non-critical subscriber %s failed for %s — continuing",
                        subscriber_cls.__name__, event.event_type,
                    )


# ── Singleton ─────────────────────────────────────────────────────────────────
_bus: EventBus = InMemoryEventBus()


def get_bus() -> EventBus:
    return _bus


def set_bus(bus: EventBus) -> None:
    """Swap the active bus (call once at startup or in tests)."""
    global _bus
    _bus = bus
