from fastapi import Depends, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from .models import User
from .repository import UserRepository, PermissionRepository, RoleRepository
from .jwt_service import decode_access_token
from .exceptions import AppException

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise AppException("Not authenticated", status_code=401, error_code="NOT_AUTHENTICATED")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as e:
        raise AppException(str(e), status_code=401, error_code="TOKEN_INVALID")

    user_id = int(payload["sub"])
    user = UserRepository(db).get_by_id(user_id)
    if not user:
        raise AppException("User not found", status_code=401, error_code="USER_NOT_FOUND")
    if not user.is_active:
        raise AppException("Account is deactivated", status_code=401, error_code="ACCOUNT_DEACTIVATED")
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
