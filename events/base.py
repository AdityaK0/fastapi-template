"""
Domain event base class and EventBus interface.

Design:
- DomainEvent is an immutable Pydantic model (frozen=True).
- EventBus is an ABC so the transport layer can be swapped without
  touching any domain code.

Transport swap path:
    InMemoryEventBus  (today)
    RedisStreamsEventBus  → change one line in bus.py
    KafkaEventBus         → change one line in bus.py
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class DomainEvent(BaseModel):
    """
    Base for every domain event. Immutable once created.

    Subclasses add their own fields:
        class UserPresent(DomainEvent):
            user_id: int
    """
    model_config = {"frozen": True}

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = Field(default_factory=datetime.now)

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


class EventBus(ABC):
    """
    Abstract event transport.

    All application code depends only on this interface.
    Infrastructure (InMemoryEventBus, RedisStreamsEventBus, etc.) is
    wired at startup — nothing in services or routes touches the concrete
    class directly.
    """

    @abstractmethod
    def publish(self, event: DomainEvent, db: Session | None = None) -> None: ...
