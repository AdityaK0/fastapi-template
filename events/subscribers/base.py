"""
Subscriber base class.

A subscriber is a plain Python class that:
    - Receives a db session in __init__ (for repository injection).
    - Implements __call__(event) to handle the event.
    - Declares critical = True/False to control error propagation.

critical = True:
    Any exception raised in __call__ will propagate out of the EventBus.
    Use for subscribers that *must* succeed (e.g. the event log itself).

critical = False (default):
    Exceptions are caught, logged, and the bus moves on to the next
    subscriber.  Use for side-effects like analytics, cache warming,
    notifications — failure must never break the primary flow.

Each subscriber is independently unit-testable by passing a mock db/repo.
Subscribers must never call each other.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from events.base import DomainEvent


class Subscriber(ABC):
    critical: bool = False

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    @abstractmethod
    def __call__(self, event: DomainEvent) -> None: ...
