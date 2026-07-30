"""
Public publishing API — the only import application code needs.

Usage:
    from events.publisher import publish
    from events.domain_events import UserPresent

    publish(UserPresent(user_id=user.id, ip_address="1.2.3.4"), db=db)

The rest of the application never imports from events.bus, events.registry,
or subscriber modules directly.  Only this module + domain_events.py.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .base import DomainEvent
from .bus import get_bus


def publish(event: DomainEvent, db: Session | None = None) -> None:
    get_bus().publish(event, db=db)
