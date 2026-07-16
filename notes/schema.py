from datetime import datetime
from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str | None = None


class NoteUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None


class NoteResponse(BaseModel):
    id: int
    title: str
    content: str | None
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
