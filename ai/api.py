from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from users.dependencies import get_current_user

from .assistant_service import TrackerAssistantService
from .creation_service import TrackerCreationService
from .proposals import TrackerProposal
from .providers.base import AIProvider
from .providers.factory import get_ai_provider
from .schema import (
    AIConfigOut,
    ConfirmProposalRequest,
    ConfirmResponse,
    ConversationOut,
    ConversationSummaryOut,
    SendMessageRequest,
    conversation_out,
)

ai_router = APIRouter(prefix="/ai", tags=["AI"])
tracker_ai_router = APIRouter(prefix="/trackers/{tracker_id}/ai", tags=["AI"])


@ai_router.get("/config", response_model=AIConfigOut)
def get_ai_config(current_user=Depends(get_current_user)):
    enabled = settings.ai_enabled
    return AIConfigOut(
        enabled=enabled,
        provider=settings.AI_PROVIDER if enabled else None,
        model=settings.AI_MODEL if enabled else None,
    )


# ── Create with AI ───────────────────────────────────────────────────────────

@ai_router.get("/tracker-conversations", response_model=list[ConversationSummaryOut])
def list_creation_conversations(
    status: str = Query("open", pattern="^(open|all)$"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TrackerCreationService(db).list(current_user.id, open_only=status == "open")


@ai_router.post("/tracker-conversations", response_model=ConversationOut, status_code=201)
def start_creation_conversation(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
):
    return conversation_out(TrackerCreationService(db, provider).start(current_user.id))


@ai_router.get("/tracker-conversations/{conversation_id}", response_model=ConversationOut)
def get_creation_conversation(conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return conversation_out(TrackerCreationService(db).get(current_user.id, conversation_id))


@ai_router.post("/tracker-conversations/{conversation_id}/messages", response_model=ConversationOut)
def send_creation_message(
    conversation_id: int,
    body: SendMessageRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
):
    service = TrackerCreationService(db, provider)
    return conversation_out(service.send_message(current_user.id, conversation_id, body.content))


@ai_router.post("/tracker-conversations/{conversation_id}/generate", response_model=ConversationOut)
def generate_tracker_proposal(
    conversation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
):
    return conversation_out(TrackerCreationService(db, provider).generate_proposal(current_user.id, conversation_id))


@ai_router.put("/tracker-conversations/{conversation_id}/proposal", response_model=ConversationOut)
def update_tracker_proposal(
    conversation_id: int,
    body: TrackerProposal,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return conversation_out(TrackerCreationService(db).update_proposal(current_user.id, conversation_id, body))


@ai_router.post("/tracker-conversations/{conversation_id}/confirm", response_model=ConfirmResponse)
def confirm_tracker_proposal(
    conversation_id: int,
    body: ConfirmProposalRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tracker_id, conversation = TrackerCreationService(db).confirm(current_user.id, conversation_id, body.proposal_version)
    return ConfirmResponse(tracker_id=tracker_id, conversation=conversation_out(conversation))


@ai_router.delete("/tracker-conversations/{conversation_id}", status_code=204)
def abandon_creation_conversation(conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    TrackerCreationService(db).abandon(current_user.id, conversation_id)


# ── Assistant for an existing tracker ────────────────────────────────────────

@tracker_ai_router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_tracker_conversations(tracker_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return TrackerAssistantService(db).list(current_user.id, tracker_id)


@tracker_ai_router.post("/conversations", response_model=ConversationOut, status_code=201)
def start_tracker_conversation(
    tracker_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
):
    return conversation_out(TrackerAssistantService(db, provider).start(current_user.id, tracker_id))


@tracker_ai_router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_tracker_conversation(tracker_id: int, conversation_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return conversation_out(TrackerAssistantService(db).get(current_user.id, tracker_id, conversation_id))


@tracker_ai_router.post("/conversations/{conversation_id}/messages", response_model=ConversationOut)
def send_tracker_message(
    tracker_id: int,
    conversation_id: int,
    body: SendMessageRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
):
    service = TrackerAssistantService(db, provider)
    return conversation_out(service.send_message(current_user.id, tracker_id, conversation_id, body.content))


@tracker_ai_router.post("/conversations/{conversation_id}/proposals/{proposal_id}/apply", response_model=ConversationOut)
def apply_tracker_proposal(
    tracker_id: int, conversation_id: int, proposal_id: int,
    current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    return conversation_out(
        TrackerAssistantService(db).apply_proposal(current_user.id, tracker_id, conversation_id, proposal_id)
    )


@tracker_ai_router.post("/conversations/{conversation_id}/proposals/{proposal_id}/dismiss", response_model=ConversationOut)
def dismiss_tracker_proposal(
    tracker_id: int, conversation_id: int, proposal_id: int,
    current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    return conversation_out(
        TrackerAssistantService(db).dismiss_proposal(current_user.id, tracker_id, conversation_id, proposal_id)
    )
