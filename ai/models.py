"""
Persistence for AI conversations.

AIConversation — one chat, owned by a user. Tracker-creation chats have no
                 tracker until one is created; assistant chats belong to a tracker.
AIMessage      — one visible user or assistant message. Only the text shown to
                 the user is stored, plus a log of tool calls (names and
                 arguments, never tool output). The model's context is rebuilt
                 from these rows on every turn.
AIProposal     — a versioned, structured plan the user can confirm: a new
                 tracker (kind=tracker_create) or a change to an existing one
                 (kind=tracker_revision). The payload is validated before it is
                 stored and again before it is applied.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConversationPurpose(str, enum.Enum):
    tracker_creation = "tracker_creation"
    tracker_assistant = "tracker_assistant"


class ConversationStatus(str, enum.Enum):
    # tracker_creation lifecycle
    discovery = "discovery"                            # waiting for the user's goal
    gathering_context = "gathering_context"            # the assistant is asking follow-ups
    awaiting_confirmation = "awaiting_confirmation"    # a proposal is on screen
    creating_tracker = "creating_tracker"              # confirm in progress (guards double submits)
    tracker_created = "tracker_created"
    # tracker_assistant lifecycle
    active = "active"
    # both
    abandoned = "abandoned"


OPEN_CREATION_STATUSES = (
    ConversationStatus.discovery,
    ConversationStatus.gathering_context,
    ConversationStatus.awaiting_confirmation,
    ConversationStatus.creating_tracker,
)


class ProposalKind(str, enum.Enum):
    tracker_create = "tracker_create"
    tracker_revision = "tracker_revision"


class ProposalStatus(str, enum.Enum):
    pending = "pending"
    applied = "applied"
    superseded = "superseded"
    dismissed = "dismissed"


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tracker_id: Mapped[int | None] = mapped_column(
        ForeignKey("trackers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="AIMessage.id", lazy="selectin",
    )
    proposals: Mapped[list["AIProposal"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="AIProposal.version", lazy="selectin",
    )


class AIProposal(Base):
    __tablename__ = "ai_proposals"
    __table_args__ = (
        UniqueConstraint("conversation_id", "version", name="uq_ai_proposal_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)   # "assistant" | "user"
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    conversation: Mapped["AIConversation"] = relationship(back_populates="proposals")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)      # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_proposals.id", ondelete="SET NULL"), nullable=True
    )
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)

    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
