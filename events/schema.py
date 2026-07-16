from datetime import date
from pydantic import BaseModel


class ActivityDay(BaseModel):
    date: date
    count: int


class ActivityResponse(BaseModel):
    data: list[ActivityDay]
    total_events: int
    start_date: date
    end_date: date
