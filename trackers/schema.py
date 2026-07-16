from datetime import date as DateType, datetime
from pydantic import BaseModel, Field
from typing import Optional
from .models import TrackerStatus


class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    position: int = 0


class HabitResponse(BaseModel):
    id: int
    name: str
    position: int

    model_config = {"from_attributes": True}


class TrackerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    duration_days: int = Field(..., ge=1, le=365)
    start_date: DateType
    habits: list[HabitCreate] = Field(default_factory=list)


class TrackerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: TrackerStatus | None = None


class ProgressUpdate(BaseModel):
    day_index: int = Field(..., ge=0)
    habit_id: int
    completed: bool


class ProgressResponse(BaseModel):
    day_index: int
    habit_id: int
    completed: bool

    model_config = {"from_attributes": True}


class TrackerSummary(BaseModel):
    id: int
    name: str
    description: str | None
    duration_days: int
    start_date: DateType
    end_date: DateType
    status: TrackerStatus
    habit_count: int
    completion_percent: float
    current_streak: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackerDetail(BaseModel):
    id: int
    name: str
    description: str | None
    duration_days: int
    start_date: DateType
    end_date: DateType
    status: TrackerStatus
    habits: list[HabitResponse]
    progress: list[ProgressResponse]
    completion_percent: float
    current_streak: int
    longest_streak: int
    completed_habits: int
    missed_habits: int
    days_elapsed: int
    days_remaining: int
    created_at: datetime

    model_config = {"from_attributes": True}
