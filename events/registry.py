"""
Subscriber registry — the explicit wiring layer.

Inspired by EVENT_ROUTES from the marketplace project:
    SUBSCRIBERS[EventType] = [SubscriberClass, SubscriberClass, ...]

Rules:
    - One place to see exactly which subscribers handle which events.
    - No magic, no decorators, no auto-discovery.
    - The bus reads this dict; nothing else does.
    - Subscriber classes are stored (not instances) — the bus instantiates
      them per-dispatch so they receive the current db session.

Adding a new event/subscriber:
    1. Define the event in domain_events.py.
    2. Define the subscriber in subscribers/.
    3. Add the mapping here.
    Done.
"""
from typing import Type

from .base import DomainEvent
from .domain_events import UserPresent
from .subscribers.event_log import EventLogSubscriber
from .subscribers.presence import PresenceProjectionSubscriber
from .subscribers.base import Subscriber

# Map event type → ordered list of subscriber classes.
# The bus instantiates each class with db= before calling it.
SUBSCRIBERS: dict[Type[DomainEvent], list[Type[Subscriber]]] = {
    UserPresent: [
        EventLogSubscriber,            # critical=True  — log first, always
        PresenceProjectionSubscriber,  # critical=False — projection, best-effort
    ],

    # Future events — uncomment when subscribers are ready:
    # TrackerCreated:   [EventLogSubscriber, XpSubscriber],
    # HabitCompleted:   [EventLogSubscriber, StreakSubscriber, XpSubscriber],
    # NoteCreated:      [EventLogSubscriber],
    # StreakBroken:     [EventLogSubscriber, NotificationSubscriber],
    # AchievementEarned:[EventLogSubscriber, NotificationSubscriber],
}


def get_subscribers(event_type: Type[DomainEvent]) -> list[Type[Subscriber]]:
    return SUBSCRIBERS.get(event_type, [])
