"""
TrackerAssistantService — "Ask AI about this tracker".

Each conversation belongs to one tracker the user owns. The model reads the
tracker only through TrackerDataToolset (bound to that user and tracker) and
can propose changes with TrackerChangeToolset; a proposal is applied only when
the user confirms it, through TrackerService.revise_structure().
"""
from __future__ import annotations

from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from config import settings
from trackers.repository import TrackerRepository
from trackers.schema import TrackerStructureUpdate
from trackers.service import TrackerService
from utils.exceptions import AppException

from . import prompts
from .engine import AIService
from .history import build_history
from .models import AIConversation, AIMessage, AIProposal, ConversationPurpose, ConversationStatus, ProposalKind, ProposalStatus, utcnow
from .proposals import describe_validation_error
from .providers.base import AIProvider, ChatMessage
from .rate_limit import enforce_ai_rate_limit
from .repository import AIConversationRepository
from .tools import CompositeToolset, TrackerChangeToolset, TrackerDataToolset, TrackerScope

PURPOSE = ConversationPurpose.tracker_assistant.value
KIND = ProposalKind.tracker_revision.value
CHANGE_FALLBACK_TEXT = "Here's a change I'd suggest. Review it below and apply it if it looks right."
MAX_ASSISTANT_CHARS = 8000


class TrackerAssistantService:
    def __init__(self, db: Session, provider: AIProvider | None = None):
        self.db = db
        self.repo = AIConversationRepository(db)
        self._provider = provider

    def _tracker(self, user_id: int, tracker_id: int):
        tracker = TrackerRepository(self.db).get_by_id(tracker_id, user_id)
        if not tracker:
            raise AppException("Tracker not found", 404, "TRACKER_NOT_FOUND")
        return tracker

    def get(self, user_id: int, tracker_id: int, conversation_id: int) -> AIConversation:
        self._tracker(user_id, tracker_id)
        conversation = self.repo.get_owned(conversation_id, user_id, PURPOSE, tracker_id=tracker_id)
        if not conversation:
            raise AppException("Conversation not found", 404, "CONVERSATION_NOT_FOUND")
        return conversation

    def list(self, user_id: int, tracker_id: int) -> list[AIConversation]:
        self._tracker(user_id, tracker_id)
        return self.repo.list_owned(user_id, PURPOSE, tracker_id=tracker_id, statuses=[ConversationStatus.active])

    def start(self, user_id: int, tracker_id: int) -> AIConversation:
        tracker = self._tracker(user_id, tracker_id)
        conversation = AIConversation(
            user_id=user_id, tracker_id=tracker_id, purpose=PURPOSE,
            status=ConversationStatus.active.value, title=tracker.name,
        )
        conversation.messages.append(AIMessage(role="assistant", content=prompts.assistant_greeting(tracker.name)))
        return self.repo.add(conversation)

    def send_message(self, user_id: int, tracker_id: int, conversation_id: int, content: str) -> AIConversation:
        conversation = self.get(user_id, tracker_id, conversation_id)
        if conversation.status != ConversationStatus.active.value:
            raise AppException("This conversation is closed. Start a new one.", 409, "CONVERSATION_CLOSED")
        if self.repo.user_turns(conversation) >= settings.AI_MAX_TURNS_PER_CONVERSATION:
            raise AppException("This conversation is at its message limit. Start a new one.", 409, "CONVERSATION_LIMIT_REACHED")
        if self._provider is None:
            raise AppException("The AI assistant isn't set up on this server.", 503, "AI_NOT_CONFIGURED")
        enforce_ai_rate_limit(self.db, user_id)

        scope = TrackerScope(self.db, user_id, tracker_id)
        toolset = CompositeToolset(TrackerDataToolset(scope), TrackerChangeToolset(scope))
        history = build_history(conversation) + [ChatMessage("user", text=content)]
        turn = AIService(self._provider).generate_response(prompts.assistant_system_prompt(date.today()), history, toolset)

        assistant_message = AIMessage(
            role="assistant",
            content=(turn.text or CHANGE_FALLBACK_TEXT)[:MAX_ASSISTANT_CHARS],
            tool_calls=turn.tool_calls or None,
            model=turn.model,
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
        )
        conversation.messages.extend([AIMessage(role="user", content=content), assistant_message])
        if turn.outcome is not None:
            self.repo.supersede_pending(conversation.id, KIND)
            proposal = AIProposal(
                kind=KIND,
                version=self.repo.next_proposal_version(conversation.id),
                source="assistant",
                status=ProposalStatus.pending.value,
                payload=turn.outcome.payload,
            )
            conversation.proposals.append(proposal)
            self.db.flush()
            assistant_message.proposal_id = proposal.id
        conversation.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def apply_proposal(self, user_id: int, tracker_id: int, conversation_id: int, proposal_id: int) -> AIConversation:
        conversation, proposal = self._pending_proposal(user_id, tracker_id, conversation_id, proposal_id)
        try:
            revision = TrackerStructureUpdate.model_validate(proposal.payload["revision"])
        except (ValidationError, KeyError, TypeError) as exc:
            detail = describe_validation_error(exc) if isinstance(exc, ValidationError) else "missing revision"
            raise AppException(f"The proposal is invalid: {detail}", 422, "INVALID_PROPOSAL")
        try:
            TrackerService(self.db).revise_structure(tracker_id, user_id, revision)
        except AppException as exc:
            if exc.error_code == "HABIT_NOT_FOUND":
                raise AppException(
                    "The tracker changed since this was proposed. Ask the assistant again.", 409, "PROPOSAL_STALE"
                )
            raise

        conversation = self.get(user_id, tracker_id, conversation_id)
        proposal = next(p for p in conversation.proposals if p.id == proposal_id)
        proposal.status = ProposalStatus.applied.value
        proposal.resolved_at = utcnow()
        conversation.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def dismiss_proposal(self, user_id: int, tracker_id: int, conversation_id: int, proposal_id: int) -> AIConversation:
        conversation, proposal = self._pending_proposal(user_id, tracker_id, conversation_id, proposal_id)
        proposal.status = ProposalStatus.dismissed.value
        proposal.resolved_at = utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def _pending_proposal(self, user_id, tracker_id, conversation_id, proposal_id) -> tuple[AIConversation, AIProposal]:
        conversation = self.get(user_id, tracker_id, conversation_id)
        proposal = next((p for p in conversation.proposals if p.id == proposal_id and p.kind == KIND), None)
        if proposal is None:
            raise AppException("Proposal not found", 404, "PROPOSAL_NOT_FOUND")
        if proposal.status != ProposalStatus.pending.value:
            raise AppException(f"This proposal was already {proposal.status}.", 409, "PROPOSAL_NOT_PENDING")
        return conversation, proposal
