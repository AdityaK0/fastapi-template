import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .models import Session as UserSession, User
from .repository import SessionRepository
from utils.security import hash_session_token

SESSION_EXPIRE_DAYS = 30


class SessionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SessionRepository(db)

    def create_session(self, user: User, request=None) -> str:
        session_token = secrets.token_urlsafe(64)

        session = UserSession(
            user_id=user.id,
            refresh_token_hash=hash_session_token(session_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS),
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )

        self.repo.create(session)
        return session_token

    def validate_session(self, session_token: str) -> UserSession | None:
        token_hash = hash_session_token(session_token)
        session = self.repo.get_by_hash(token_hash)

        if not session:
            return None

        if session.revoked_at is not None:
            return None

        now = datetime.now(timezone.utc)
        expires = session.expires_at
        # make aware if stored naive (legacy rows)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires < now:
            self.repo.delete_expired()
            return None

        self.repo.touch(session)
        return session

    def get_user_from_session(self, session_token: str) -> User | None:
        session = self.validate_session(session_token)
        if not session:
            return None
        return session.user

    def revoke_session(self, session_token: str) -> bool:
        token_hash = hash_session_token(session_token)
        session = self.repo.get_by_hash(token_hash)
        if not session:
            return False
        self.repo.revoke(session)
        return True

    def revoke_all_sessions(self, user_id: int) -> None:
        self.repo.revoke_all_for_user(user_id)

    def cleanup_expired_sessions(self) -> int:
        return self.repo.delete_expired()
