"""
Application-level event and entity type enums.

Kept as Python enums (not PostgreSQL enums) so new values can be added
without any database migration — just extend the class.

EventType  — what happened
EntityType — which resource it happened to
"""
from enum import Enum


class EventType(str, Enum):
    # Auth
    USER_LOGIN = "USER_LOGIN"

    # Future — add here, no DB migration needed
    # USER_REGISTERED    = "USER_REGISTERED"
    # USER_PASSWORD_CHANGED = "USER_PASSWORD_CHANGED"

    # Trackers
    # TRACKER_CREATED    = "TRACKER_CREATED"
    # TRACKER_UPDATED    = "TRACKER_UPDATED"
    # TRACKER_DELETED    = "TRACKER_DELETED"
    # TRACKER_COMPLETED  = "TRACKER_COMPLETED"
    # TRACKER_RESTORED   = "TRACKER_RESTORED"

    # Habits
    # HABIT_COMPLETED    = "HABIT_COMPLETED"
    # HABIT_UNCHECKED    = "HABIT_UNCHECKED"

    # Notes
    # NOTE_CREATED       = "NOTE_CREATED"
    # NOTE_UPDATED       = "NOTE_UPDATED"
    # NOTE_DELETED       = "NOTE_DELETED"
    # NOTE_RESTORED      = "NOTE_RESTORED"

    # Future features
    # FOLDER_CREATED     = "FOLDER_CREATED"
    # TAG_CREATED        = "TAG_CREATED"
    # STREAK_BROKEN      = "STREAK_BROKEN"
    # ACHIEVEMENT_EARNED = "ACHIEVEMENT_EARNED"


class EntityType(str, Enum):
    USER    = "user"
    TRACKER = "tracker"
    NOTE    = "note"
    HABIT   = "habit"
    FOLDER  = "folder"
    TAG     = "tag"
