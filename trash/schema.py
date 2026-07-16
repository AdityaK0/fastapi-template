from datetime import datetime
from pydantic import BaseModel


class TrashedItem(BaseModel):
    id: int
    type: str  # "note" | "tracker"
    title: str
    deleted_at: datetime

    model_config = {"from_attributes": True}


class TrashResponse(BaseModel):
    notes: list[TrashedItem]
    trackers: list[TrashedItem]
    total: int
