from pydantic import BaseModel
from datetime import datetime


class DashboardStats(BaseModel):
    total_trackers: int
    active_trackers: int
    completed_trackers: int
    upcoming_trackers: int
    total_notes: int
    pinned_notes: int
    today_completion_percent: float
