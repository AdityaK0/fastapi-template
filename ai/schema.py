from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

from config import settings

from .models import AIConversation, AIProposal, ProposalStatus


def _as_utc(value: datetime | None) -> datetime | None:
    # Stored as naive UTC; attach the zone so clients don't read it as local time.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def _check(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message can't be empty")
        if len(value) > settings.AI_MAX_MESSAGE_CHARS:
            raise ValueError(f"Message is too long (max {settings.AI_MAX_MESSAGE_CHARS} characters)")
        return value


class ConfirmProposalRequest(BaseModel):
    proposal_version: int = Field(..., ge=1)


class ProposalOut(BaseModel):
    id: int
    kind: str
    version: int
    source: str
    status: str
    payload: dict
    created_at: UTCDateTime
    resolved_at: UTCDateTime | None = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    proposal_id: int | None
    created_at: UTCDateTime

    model_config = {"from_attributes": True}


class ConversationSummaryOut(BaseModel):
    id: int
    purpose: str
    status: str
    tracker_id: int | None
    title: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime

    model_config = {"from_attributes": True}


class ConversationOut(ConversationSummaryOut):
    messages: list[MessageOut]
    proposals: list[ProposalOut]
    current_proposal: ProposalOut | None = None


class ConfirmResponse(BaseModel):
    tracker_id: int
    conversation: ConversationOut


class AIConfigOut(BaseModel):
    enabled: bool
    provider: str | None
    model: str | None


def conversation_out(conversation: AIConversation) -> ConversationOut:
    pending: list[AIProposal] = [p for p in conversation.proposals if p.status == ProposalStatus.pending.value]
    return ConversationOut(
        id=conversation.id,
        purpose=conversation.purpose,
        status=conversation.status,
        tracker_id=conversation.tracker_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[MessageOut.model_validate(m) for m in conversation.messages],
        proposals=[ProposalOut.model_validate(p) for p in conversation.proposals],
        current_proposal=ProposalOut.model_validate(pending[-1]) if pending else None,
    )
