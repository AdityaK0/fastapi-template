"""Conversation queries. Every lookup is scoped to the owning user."""
from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import AIConversation, AIMessage, AIProposal, ProposalStatus, utcnow


class AIConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_owned(self, conversation_id: int, user_id: int, purpose: str, tracker_id: int | None = None) -> AIConversation | None:
        q = select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.user_id == user_id,
            AIConversation.purpose == purpose,
        )
        if tracker_id is not None:
            q = q.where(AIConversation.tracker_id == tracker_id)
        return self.db.scalar(q)

    def list_owned(self, user_id: int, purpose: str, *, statuses=None, tracker_id: int | None = None, limit: int = 20) -> list[AIConversation]:
        q = select(AIConversation).where(AIConversation.user_id == user_id, AIConversation.purpose == purpose)
        if statuses:
            q = q.where(AIConversation.status.in_([s.value if hasattr(s, "value") else s for s in statuses]))
        if tracker_id is not None:
            q = q.where(AIConversation.tracker_id == tracker_id)
        q = q.order_by(AIConversation.updated_at.desc(), AIConversation.id.desc()).limit(limit)
        return list(self.db.scalars(q).all())

    def add(self, conversation: AIConversation) -> AIConversation:
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def claim_status(self, conversation_id: int, expected: str, new: str) -> bool:
        """Atomically move a conversation between statuses; False if another request got there first."""
        result = self.db.execute(
            update(AIConversation)
            .where(AIConversation.id == conversation_id, AIConversation.status == expected)
            .values(status=new, updated_at=utcnow())
        )
        self.db.commit()
        return result.rowcount == 1

    def user_turns(self, conversation: AIConversation) -> int:
        return sum(1 for m in conversation.messages if m.role == "user")

    def next_proposal_version(self, conversation_id: int) -> int:
        current = self.db.scalar(
            select(func.max(AIProposal.version)).where(AIProposal.conversation_id == conversation_id)
        )
        return (current or 0) + 1

    def supersede_pending(self, conversation_id: int, kind: str) -> None:
        self.db.execute(
            update(AIProposal)
            .where(
                AIProposal.conversation_id == conversation_id,
                AIProposal.kind == kind,
                AIProposal.status == ProposalStatus.pending.value,
            )
            .values(status=ProposalStatus.superseded.value, resolved_at=utcnow())
        )

    @staticmethod
    def current_proposal(conversation: AIConversation, kind: str) -> AIProposal | None:
        pending = [p for p in conversation.proposals if p.kind == kind and p.status == ProposalStatus.pending.value]
        return pending[-1] if pending else None

    def add_messages(self, *messages: AIMessage) -> None:
        self.db.add_all(messages)
