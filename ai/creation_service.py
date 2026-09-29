"""
TrackerCreationService — the "Create with AI" conversation.

discovery ──user message──▶ gathering_context ──propose_tracker──▶ awaiting_confirmation
                                   ▲                                   │  │ chat / edit → new proposal version
                                   └───── follow-up questions ─────────┘  │
awaiting_confirmation ──confirm──▶ creating_tracker ──TrackerService.create()──▶ tracker_created
any open state ──abandon──▶ abandoned

The assistant never creates a tracker. Confirmation converts the stored
proposal into a TrackerCreate and calls the same TrackerService.create() as
the manual wizard.
"""
from __future__ import annotations

import logging
from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from config import settings
from trackers.service import TrackerService
from utils.exceptions import AppException

from . import prompts
from .engine import AIService
from .history import build_history
from .models import (
    OPEN_CREATION_STATUSES,
    AIConversation,
    AIMessage,
    AIProposal,
    ConversationPurpose,
    ConversationStatus,
    ProposalKind,
    ProposalStatus,
    utcnow,
)
from .proposals import TrackerProposal, describe_validation_error
from .providers.base import AIProvider, ChatMessage
from .rate_limit import enforce_ai_rate_limit
from .repository import AIConversationRepository
from .tools import TrackerProposalToolset

logger = logging.getLogger(__name__)

PURPOSE = ConversationPurpose.tracker_creation.value
KIND = ProposalKind.tracker_create.value
CHAT_STATUSES = {
    ConversationStatus.discovery.value,
    ConversationStatus.gathering_context.value,
    ConversationStatus.awaiting_confirmation.value,
}
PROPOSAL_FALLBACK_TEXT = "Here's a tracker based on what you've told me. Does this look right?"
MAX_ASSISTANT_CHARS = 8000


class TrackerCreationService:
    def __init__(self, db: Session, provider: AIProvider | None = None):
        self.db = db
        self.repo = AIConversationRepository(db)
        self._provider = provider

    # ── queries ──────────────────────────────────────────────────────────────

    def get(self, user_id: int, conversation_id: int) -> AIConversation:
        conversation = self.repo.get_owned(conversation_id, user_id, PURPOSE)
        if not conversation:
            raise AppException("Conversation not found", 404, "CONVERSATION_NOT_FOUND")
        return conversation

    def list(self, user_id: int, open_only: bool) -> list[AIConversation]:
        return self.repo.list_owned(user_id, PURPOSE, statuses=OPEN_CREATION_STATUSES if open_only else None)

    # ── commands ─────────────────────────────────────────────────────────────

    def start(self, user_id: int) -> AIConversation:
        conversation = AIConversation(user_id=user_id, purpose=PURPOSE, status=ConversationStatus.discovery.value)
        conversation.messages.append(AIMessage(role="assistant", content=prompts.CREATION_GREETING))
        return self.repo.add(conversation)

    def send_message(self, user_id: int, conversation_id: int, content: str) -> AIConversation:
        conversation = self._open_for_chat(user_id, conversation_id)
        return self._run_turn(conversation, content, require_proposal=False)

    def generate_proposal(self, user_id: int, conversation_id: int) -> AIConversation:
        conversation = self._open_for_chat(user_id, conversation_id)
        if self.repo.user_turns(conversation) == 0:
            raise AppException("Tell the assistant about your goal first.", 409, "INVALID_CONVERSATION_STATE")
        return self._run_turn(conversation, prompts.GENERATE_NOW_MESSAGE, require_proposal=True)

    def update_proposal(self, user_id: int, conversation_id: int, proposal: TrackerProposal) -> AIConversation:
        conversation = self.get(user_id, conversation_id)
        if conversation.status != ConversationStatus.awaiting_confirmation.value:
            raise AppException("There's no proposal to edit yet.", 409, "INVALID_CONVERSATION_STATE")
        self._check_start_date(proposal)
        self._store_proposal(conversation, proposal, source="user")
        conversation.title = proposal.name
        conversation.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def confirm(self, user_id: int, conversation_id: int, proposal_version: int) -> tuple[int, AIConversation]:
        conversation = self.get(user_id, conversation_id)
        if conversation.status == ConversationStatus.tracker_created.value and conversation.tracker_id:
            applied = [p for p in conversation.proposals if p.status == ProposalStatus.applied.value]
            if applied and applied[-1].version == proposal_version:
                return conversation.tracker_id, conversation   # repeated confirm (double click, retry)
        if conversation.status == ConversationStatus.creating_tracker.value:
            raise AppException("This tracker is already being created.", 409, "CONFIRMATION_IN_PROGRESS")
        if conversation.status != ConversationStatus.awaiting_confirmation.value:
            raise AppException("There's no proposal waiting for confirmation.", 409, "INVALID_CONVERSATION_STATE")

        stored = self.repo.current_proposal(conversation, KIND)
        if stored is None or stored.version != proposal_version:
            raise AppException(
                "The proposal changed. Review the latest version before creating the tracker.",
                409, "PROPOSAL_VERSION_MISMATCH",
            )
        try:
            proposal = TrackerProposal.model_validate(stored.payload)
        except ValidationError as exc:
            raise AppException(f"The proposal is invalid: {describe_validation_error(exc)}", 422, "INVALID_PROPOSAL")
        self._check_start_date(proposal)

        if not self.repo.claim_status(conversation.id, ConversationStatus.awaiting_confirmation.value,
                                      ConversationStatus.creating_tracker.value):
            raise AppException("This tracker is already being created.", 409, "CONFIRMATION_IN_PROGRESS")
        try:
            tracker = TrackerService(self.db).create(user_id, proposal.to_tracker_create())
        except Exception:
            self.db.rollback()
            self.repo.claim_status(conversation.id, ConversationStatus.creating_tracker.value,
                                   ConversationStatus.awaiting_confirmation.value)
            raise

        conversation = self.get(user_id, conversation_id)
        stored = next(p for p in conversation.proposals if p.id == stored.id)
        stored.status = ProposalStatus.applied.value
        stored.resolved_at = utcnow()
        conversation.status = ConversationStatus.tracker_created.value
        conversation.tracker_id = tracker.id
        conversation.title = tracker.name
        conversation.messages.append(AIMessage(
            role="assistant",
            content=f"Your tracker “{tracker.name}” is ready. Check off today's habits whenever you've done them.",
        ))
        self.db.commit()
        self.db.refresh(conversation)
        return tracker.id, conversation

    def abandon(self, user_id: int, conversation_id: int) -> None:
        conversation = self.get(user_id, conversation_id)
        if conversation.status in CHAT_STATUSES:
            conversation.status = ConversationStatus.abandoned.value
            self.repo.supersede_pending(conversation.id, KIND)
            self.db.commit()

    # ── internals ────────────────────────────────────────────────────────────

    def _open_for_chat(self, user_id: int, conversation_id: int) -> AIConversation:
        conversation = self.get(user_id, conversation_id)
        if conversation.status not in CHAT_STATUSES:
            raise AppException("This conversation is closed. Start a new one.", 409, "CONVERSATION_CLOSED")
        if self.repo.user_turns(conversation) >= settings.AI_MAX_TURNS_PER_CONVERSATION:
            raise AppException("This conversation is at its message limit. Start a new one.", 409, "CONVERSATION_LIMIT_REACHED")
        return conversation

    def _run_turn(self, conversation: AIConversation, content: str, *, require_proposal: bool) -> AIConversation:
        if self._provider is None:
            raise AppException("The AI assistant isn't set up on this server.", 503, "AI_NOT_CONFIGURED")
        enforce_ai_rate_limit(self.db, conversation.user_id)

        today = date.today()
        current = self.repo.current_proposal(conversation, KIND)
        system = prompts.creation_system_prompt(
            today,
            current.payload if current else None,
            current.version if current else None,
            edited_by_user=bool(current and current.source == "user"),
        )
        history = build_history(conversation) + [ChatMessage("user", text=content)]
        toolset = TrackerProposalToolset(today)
        service = AIService(self._provider)
        if require_proposal:
            turn = service.generate_structured_output(system, history, toolset, TrackerProposalToolset.NAME)
        else:
            turn = service.generate_response(system, history, toolset)

        user_message = AIMessage(role="user", content=content)
        assistant_message = AIMessage(
            role="assistant",
            content=(turn.text or PROPOSAL_FALLBACK_TEXT)[:MAX_ASSISTANT_CHARS],
            tool_calls=turn.tool_calls or None,
            model=turn.model,
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
        )
        conversation.messages.extend([user_message, assistant_message])

        if turn.outcome is not None:
            proposal = self._store_proposal(conversation, turn.outcome.payload, source="assistant")
            self.db.flush()
            assistant_message.proposal_id = proposal.id
            conversation.title = turn.outcome.payload.name
        elif conversation.status == ConversationStatus.discovery.value:
            conversation.status = ConversationStatus.gathering_context.value
            conversation.title = content[:80]
        conversation.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def _store_proposal(self, conversation: AIConversation, proposal: TrackerProposal, *, source: str) -> AIProposal:
        self.repo.supersede_pending(conversation.id, KIND)
        stored = AIProposal(
            kind=KIND,
            version=self.repo.next_proposal_version(conversation.id),
            source=source,
            status=ProposalStatus.pending.value,
            payload=proposal.model_dump(mode="json"),
        )
        conversation.proposals.append(stored)
        conversation.status = ConversationStatus.awaiting_confirmation.value
        return stored

    @staticmethod
    def _check_start_date(proposal: TrackerProposal) -> None:
        if proposal.start_date < date.today():
            raise AppException(
                "The start date is in the past. Pick today or a later date.", 422, "PROPOSAL_START_DATE_PAST"
            )
