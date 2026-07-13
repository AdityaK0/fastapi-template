from fastapi import Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from .models import User
from .session_service import SessionService
from .repository import PermissionRepository, RoleRepository
from .exceptions import AppException


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    session_token = request.cookies.get("session_id")
    if not session_token:
        raise AppException("Not authenticated", status_code=401, error_code="NOT_AUTHENTICATED")

    user = SessionService(db).get_user_from_session(session_token)
    if not user:
        raise AppException("Invalid or expired session", status_code=401, error_code="SESSION_INVALID")

    return user


def require_role(role_name: str):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_roles = {r.name for r in RoleRepository(db).get_user_roles(current_user)}
        if role_name not in user_roles:
            raise AppException(f"Role '{role_name}' required", status_code=403, error_code="FORBIDDEN")
        return current_user

    return dependency


def require_permission(permission_name: str):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        permissions = PermissionRepository(db).get_user_permissions(current_user)
        if permission_name not in permissions:
            raise AppException(f"Permission '{permission_name}' required", status_code=403, error_code="FORBIDDEN")
        return current_user

    return dependency
