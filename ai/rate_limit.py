"""Per-user limits on AI messages, counted from stored messages so they hold across workers."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from utils.exceptions import AppException

from .models import AIConversation, AIMessage, utcnow


def _user_messages_since(db: Session, user_id: int, since) -> int:
    return db.scalar(
        select(func.count(AIMessage.id))
        .join(AIConversation, AIConversation.id == AIMessage.conversation_id)
        .where(AIConversation.user_id == user_id, AIMessage.role == "user", AIMessage.created_at >= since)
    ) or 0


def enforce_ai_rate_limit(db: Session, user_id: int) -> None:
    now = utcnow()
    if _user_messages_since(db, user_id, now - timedelta(minutes=1)) >= settings.AI_RATE_LIMIT_PER_MINUTE:
        raise AppException(
            "You're sending messages faster than the assistant can keep up. Wait a minute and try again.",
            429, "AI_RATE_LIMITED",
        )
    if _user_messages_since(db, user_id, now - timedelta(days=1)) >= settings.AI_RATE_LIMIT_PER_DAY:
        raise AppException(
            "You've reached today's limit for assistant messages. Try again tomorrow.",
            429, "AI_RATE_LIMITED",
        )
