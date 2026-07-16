from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .models import User
from .repository import UserRepository, RoleRepository, PermissionRepository
from .session_service import SessionService
from .exceptions import AppException
from utils.security import hash_password, verify_password


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.role_repo = RoleRepository(db)
        self.perm_repo = PermissionRepository(db)
        self.session_service = SessionService(db)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.user_repo.get_by_username(username)
        if user and verify_password(password, user.hashed_password):
            return user
        return None

    def register(self, data) -> User:
        if self.user_repo.get_by_username(data.username):
            raise AppException("Username already exists", status_code=422, error_code="USERNAME_TAKEN")

        if self.user_repo.get_by_email(data.email):
            raise AppException("Email already exists", status_code=422, error_code="EMAIL_TAKEN")

        if data.phone_number and self.user_repo.get_by_phone(data.phone_number):
            raise AppException("Phone number already registered", status_code=422, error_code="PHONE_TAKEN")

        user = User(
            fullname=data.fullname,
            email=data.email,
            username=data.username,
            phone_number=data.phone_number,
            hashed_password=hash_password(data.password),
        )
        return self.user_repo.create(user)

    def login(self, command, request=None) -> str:
        user = self.authenticate(command.username, command.password)
        if not user:
            raise AppException("Invalid username or password", status_code=401, error_code="INVALID_CREDENTIALS")
        if not user.is_active:
            raise AppException("Account is deactivated", status_code=401, error_code="ACCOUNT_DEACTIVATED")
        user.last_login = datetime.now(timezone.utc)
        self.user_repo.update(user)
        return self.session_service.create_session(user=user, request=request)

    def logout(self, session_token: str) -> None:
        self.session_service.revoke_session(session_token)

    def logout_all_devices(self, user_id: int) -> None:
        self.session_service.revoke_all_sessions(user_id)

    def get_current_user(self, session_token: str) -> User | None:
        return self.session_service.get_user_from_session(session_token)

    def update_profile(self, user: User, data) -> User:
        if data.fullname is not None:
            user.fullname = data.fullname
        if data.phone_number is not None:
            existing = self.user_repo.get_by_phone(data.phone_number)
            if existing and existing.id != user.id:
                raise AppException("Phone number already registered", status_code=422, error_code="PHONE_TAKEN")
            user.phone_number = data.phone_number
        return self.user_repo.update(user)

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise AppException("Current password is incorrect", status_code=401, error_code="WRONG_PASSWORD")
        user.hashed_password = hash_password(new_password)
        self.user_repo.update(user)

    def deactivate_user(self, user_id: int) -> User:
        target = self.user_repo.get_by_id(user_id)
        if not target:
            raise AppException("User not found", status_code=404, error_code="USER_NOT_FOUND")
        target.is_active = False
        self.user_repo.update(target)
        self.session_service.revoke_all_sessions(user_id)
        return target

    def assign_role(self, user_id: int, role_name: str) -> None:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise AppException("User not found", status_code=404, error_code="USER_NOT_FOUND")
        role = self.role_repo.get_by_name(role_name)
        if not role:
            raise AppException(f"Role '{role_name}' not found", status_code=404, error_code="ROLE_NOT_FOUND")
        self.role_repo.assign_role(user, role)

    def get_user_permissions(self, user: User) -> set[str]:
        return self.perm_repo.get_user_permissions(user)

    def update_profile_extended(self, user: User, data) -> User:
        """Update extended profile fields."""
        fields = ['display_name', 'first_name', 'last_name', 'bio', 'website', 'location']
        for field in fields:
            val = getattr(data, field, None)
            if val is not None:
                setattr(user, field, val)

        if data.username is not None and data.username != user.username:
            existing = self.user_repo.get_by_username(data.username)
            if existing and existing.id != user.id:
                raise AppException("Username already taken", status_code=422, error_code="USERNAME_TAKEN")
            user.username = data.username

        if data.phone_number is not None:
            existing = self.user_repo.get_by_phone(data.phone_number)
            if existing and existing.id != user.id:
                raise AppException("Phone number already registered", status_code=422, error_code="PHONE_TAKEN")
            user.phone_number = data.phone_number

        return self.user_repo.update(user)

    def update_avatar(self, user: User, avatar_path: str) -> User:
        from .avatar_service import avatar_storage
        if user.avatar_path:
            avatar_storage.delete(user.avatar_path)
        user.avatar_path = avatar_path
        return self.user_repo.update(user)

    def delete_avatar(self, user: User) -> User:
        from .avatar_service import avatar_storage
        if user.avatar_path:
            avatar_storage.delete(user.avatar_path)
        user.avatar_path = None
        return self.user_repo.update(user)
