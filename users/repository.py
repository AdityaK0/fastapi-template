from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from .models import User, Session as UserSession, Role, Permission


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_phone(self, phone_number: str) -> User | None:
        return self.db.scalar(
            select(User).where(User.phone_number == phone_number)
        )

    def update(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, session: UserSession) -> UserSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_hash(self, token_hash: str) -> UserSession | None:
        return self.db.scalar(
            select(UserSession).where(
                UserSession.refresh_token_hash == token_hash
            )
        )

    def revoke(self, session: UserSession) -> None:
        session.revoked_at = datetime.now(timezone.utc)
        self.db.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        sessions = self.db.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
        ).all()
        now = datetime.now(timezone.utc)
        for s in sessions:
            s.revoked_at = now
        self.db.commit()

    def delete_expired(self) -> int:
        now = datetime.now(timezone.utc)
        result = self.db.execute(
            delete(UserSession).where(UserSession.expires_at < now)
        )
        self.db.commit()
        return result.rowcount

    def touch(self, session: UserSession) -> None:
        session.last_used_at = datetime.now(timezone.utc)
        self.db.commit()


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))

    def get_all(self) -> list[Role]:
        return list(self.db.scalars(select(Role)).all())

    def assign_role(self, user: User, role: Role) -> None:
        if role not in user.roles:
            user.roles.append(role)
            self.db.commit()

    def remove_role(self, user: User, role: Role) -> None:
        if role in user.roles:
            user.roles.remove(role)
            self.db.commit()

    def get_user_roles(self, user: User) -> list[Role]:
        return list(user.roles)


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, name: str) -> Permission | None:
        return self.db.scalar(select(Permission).where(Permission.name == name))

    def get_user_permissions(self, user: User) -> set[str]:
        permissions: set[str] = set()
        for role in user.roles:
            for perm in role.permissions:
                permissions.add(perm.name)
        return permissions
