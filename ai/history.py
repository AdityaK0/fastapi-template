"""Rebuilds the model's context from stored messages, within the configured window."""
from __future__ import annotations

from config import settings

from .models import AIConversation, AIMessage, AIProposal, ProposalKind
from .providers.base import ChatMessage


def _render(message: AIMessage, proposals: dict[int, AIProposal]) -> str:
    text = message.content
    proposal = proposals.get(message.proposal_id) if message.proposal_id else None
    if proposal is None:
        return text
    if proposal.kind == ProposalKind.tracker_create.value:
        return f"{text}\n\n[You showed the user tracker proposal version {proposal.version}.]"
    summary = proposal.payload.get("summary", "")
    return f"{text}\n\n[You proposed a tracker change: {summary} The user's decision: {proposal.status}.]"


def build_history(conversation: AIConversation, max_messages: int | None = None) -> list[ChatMessage]:
    """
    The most recent messages as ChatMessages, oldest first.

    Greetings before the user's first message are dropped (the model API wants a
    user message first). When the window is full, the user's first message is
    kept because it usually states the goal.
    """
    limit = max(max_messages or settings.AI_CONTEXT_MAX_MESSAGES, 2)
    proposals = {p.id: p for p in conversation.proposals}
    stored = [m for m in conversation.messages if m.content.strip()]
    while stored and stored[0].role != "user":
        stored.pop(0)
    if len(stored) > limit:
        stored = stored[:1] + stored[-(limit - 1):]
    return [ChatMessage(role=m.role, text=_render(m, proposals)) for m in stored]
