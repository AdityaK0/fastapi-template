"""
All domain events for HabitFlow.

Convention:
    - Past-tense noun phrase: UserPresent, TrackerCompleted, HabitChecked.
    - Immutable fields only.
    - Add future events here, then wire subscribers in registry.py.

Adding a new event:
    1. Define the class below.
    2. Add subscriber classes in events/subscribers/.
    3. Register: SUBSCRIBERS[NewEvent] = [NewSubscriber()] in registry.py.
    4. Call EventBus.publish(NewEvent(...), db=db) where the action occurs.
    No migration needed — event_type is stored as a plain string.
"""
from .base import DomainEvent


class UserPresent(DomainEvent):
    """
    A user successfully authenticated.
    Published on every successful login.

    Triggers:
        EventLogSubscriber         — appends a row to event_logs
        PresenceProjectionSubscriber — upserts daily_presence (heatmap)
    """
    user_id: int
    ip_address: str | None = None
    user_agent: str | None = None


# ── Future events (uncomment + add to registry when ready) ────────────────────

# class TrackerCreated(DomainEvent):
#     user_id: int
#     tracker_id: int
#     name: str
#     duration_days: int

# class TrackerCompleted(DomainEvent):
#     user_id: int
#     tracker_id: int

# class TrackerDeleted(DomainEvent):
#     user_id: int
#     tracker_id: int

# class HabitCompleted(DomainEvent):
#     user_id: int
#     tracker_id: int
#     habit_id: int
#     day_index: int

# class HabitUnchecked(DomainEvent):
#     user_id: int
#     tracker_id: int
#     habit_id: int
#     day_index: int

# class NoteCreated(DomainEvent):
#     user_id: int
#     note_id: int

# class NoteUpdated(DomainEvent):
#     user_id: int
#     note_id: int

# class NoteDeleted(DomainEvent):
#     user_id: int
#     note_id: int

# class StreakBroken(DomainEvent):
#     user_id: int
#     tracker_id: int
#     streak_length: int

# class AchievementEarned(DomainEvent):
#     user_id: int
#     achievement_key: str
