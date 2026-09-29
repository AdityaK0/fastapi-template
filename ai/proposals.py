"""
Structured contracts the AI produces.

TrackerProposal is the existing TrackerCreate schema with tighter limits, so any
valid proposal converts losslessly into the payload manual creation sends and
goes through the same TrackerService.create().

TrackerChangeProposal wraps the domain's TrackerStructureUpdate with a short
summary the user sees on the proposal card.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from trackers.schema import HabitCreate, HabitStructureItem, TrackerCreate, TrackerStructureUpdate

MAX_PROPOSED_HABITS = 12


class ProposedHabit(HabitCreate):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    position: int = 0

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class TrackerProposal(TrackerCreate):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    duration_days: int = Field(..., ge=1, le=365)
    start_date: date
    habits: list[ProposedHabit] = Field(..., min_length=1, max_length=MAX_PROPOSED_HABITS)

    @field_validator("name", "description", mode="before")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _normalise_habits(self):
        names = [h.name.lower() for h in self.habits]
        if len(set(names)) != len(names):
            raise ValueError("habit names must be unique")
        # Order in the list is the order shown to the user.
        for position, habit in enumerate(self.habits):
            habit.position = position
        return self

    def to_tracker_create(self) -> TrackerCreate:
        return TrackerCreate(
            name=self.name,
            description=self.description,
            duration_days=self.duration_days,
            start_date=self.start_date,
            habits=[HabitCreate(name=h.name, position=h.position) for h in self.habits],
        )


class ProposedHabitChange(HabitStructureItem):
    model_config = ConfigDict(extra="forbid")


class TrackerChangeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1, max_length=500)
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=1000)
    habits: list[ProposedHabitChange] = Field(..., min_length=1, max_length=50)

    @field_validator("summary", "name", mode="before")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    def to_structure_update(self) -> TrackerStructureUpdate:
        return TrackerStructureUpdate(
            name=self.name,
            description=self.description,
            habits=[HabitStructureItem(habit_id=h.habit_id, name=h.name.strip()) for h in self.habits],
        )


def describe_validation_error(exc: ValidationError, limit: int = 5) -> str:
    parts = []
    for err in exc.errors()[:limit]:
        location = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{location}: {err.get('msg')}" if location else str(err.get("msg")))
    return "; ".join(parts)


# JSON Schemas for the proposal tools. Strict tool schemas can't carry length or
# range constraints, so those are stated in descriptions and enforced by the
# Pydantic models above when the tool call arrives.
_NULLABLE_STRING = {"anyOf": [{"type": "string"}, {"type": "null"}]}

TRACKER_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "description", "duration_days", "start_date", "habits"],
    "properties": {
        "name": {"type": "string", "description": "Tracker title, up to 200 characters, e.g. '30-Day Reading Habit'."},
        "description": {**_NULLABLE_STRING, "description": "One or two sentences on what the tracker is for, or null."},
        "duration_days": {"type": "integer", "description": "Number of days the tracker runs, 1-365."},
        "start_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD. Today or later."},
        "habits": {
            "type": "array",
            "description": f"1-{MAX_PROPOSED_HABITS} daily habits in display order. Names must be unique.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "A daily action the user checks off, under 60 characters."},
                },
            },
        },
    },
}

TRACKER_CHANGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "name", "description", "habits"],
    "properties": {
        "summary": {"type": "string", "description": "One or two sentences shown on the proposal card explaining the change."},
        "name": {**_NULLABLE_STRING, "description": "New tracker name, or null to keep the current one."},
        "description": {**_NULLABLE_STRING, "description": "New description, or null to keep the current one."},
        "habits": {
            "type": "array",
            "description": (
                "The complete ordered list of habits to keep, using habit_id values from "
                "get_tracker_overview. Leave a habit out to remove it. Change name to rename it. "
                "New habits can't be added."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["habit_id", "name"],
                "properties": {
                    "habit_id": {"type": "integer"},
                    "name": {"type": "string", "description": "Habit name (unchanged or new), under 60 characters."},
                },
            },
        },
    },
}
