from fastapi import APIRouter, Depends, Request, File, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from config import settings
from .schema import CreateUser, LoginSchema, UpdateProfileSchema, ChangePasswordSchema, UserResponse, ProfileUpdateSchema, FullProfileResponse
from .service import UserService
from .dependencies import get_current_user, require_permission
from .permissions import USER_UPDATE, USER_DEACTIVATE, ROLE_ASSIGN
from .jwt_service import create_access_token, create_refresh_token
from .session_service import SessionService
from .avatar_service import avatar_storage
from utils.security import hash_session_token

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
user_router = APIRouter(prefix="/users", tags=["Users"])


@auth_router.post("/register")
def register(data: CreateUser, db: Session = Depends(get_db)):
    user = UserService(db).register(data)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    # Store refresh token hashed in sessions table
    from datetime import datetime, timedelta, timezone
    from .models import Session as UserSession
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_session_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "fullname": user.fullname,
            "email": user.email,
        },
    }


@auth_router.post("/login")
def login(command: LoginSchema, request: Request, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta, timezone
    from .models import Session as UserSession
    user = UserService(db).authenticate(command.username, command.password)
    if not user:
        from .exceptions import AppException
        raise AppException("Invalid username or password", status_code=401, error_code="INVALID_CREDENTIALS")
    if not user.is_active:
        from .exceptions import AppException
        raise AppException("Account is deactivated", status_code=401, error_code="ACCOUNT_DEACTIVATED")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_session_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "fullname": user.fullname,
            "email": user.email,
        },
    }


@auth_router.post("/refresh")
def refresh_token(body: dict, db: Session = Depends(get_db)):
    from .exceptions import AppException
    token = body.get("refresh_token")
    if not token:
        raise AppException("Refresh token required", status_code=400, error_code="MISSING_TOKEN")
    session = SessionService(db).validate_session(token)
    if not session:
        raise AppException("Invalid or expired refresh token", status_code=401, error_code="TOKEN_INVALID")
    new_access_token = create_access_token(session.user_id)
    return {"access_token": new_access_token, "token_type": "bearer"}


@auth_router.post("/logout")
def logout(body: dict, db: Session = Depends(get_db)):
    token = body.get("refresh_token", "")
    if token:
        SessionService(db).revoke_session(token)
    return {"message": "Logged out successfully"}


@auth_router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    return current_user


# Keep backward-compatible user management endpoints
@user_router.patch("/profile")
def update_profile(data: UpdateProfileSchema, current_user=Depends(require_permission(USER_UPDATE)), db: Session = Depends(get_db)):
    user = UserService(db).update_profile(current_user, data)
    return {"message": "Profile updated", "username": user.username, "fullname": user.fullname}


@user_router.post("/change-password")
def change_password(data: ChangePasswordSchema, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    UserService(db).change_password(current_user, data.current_password, data.new_password)
    return {"message": "Password changed successfully"}


@user_router.post("/{user_id}/deactivate")
def deactivate_user(user_id: int, current_user=Depends(require_permission(USER_DEACTIVATE)), db: Session = Depends(get_db)):
    UserService(db).deactivate_user(user_id)
    return {"message": f"User {user_id} deactivated"}


@user_router.post("/{user_id}/assign-role")
def assign_role(user_id: int, role_name: str, current_user=Depends(require_permission(ROLE_ASSIGN)), db: Session = Depends(get_db)):
    UserService(db).assign_role(user_id, role_name)
    return {"message": f"Role '{role_name}' assigned to user {user_id}"}


@user_router.get("/me", response_model=FullProfileResponse)
def get_my_profile(current_user=Depends(get_current_user)):
    return current_user


@user_router.patch("/me", response_model=FullProfileResponse)
def update_my_profile(
    data: ProfileUpdateSchema,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserService(db).update_profile_extended(current_user, data)


@user_router.post("/avatar", response_model=FullProfileResponse)
def upload_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    path = avatar_storage.save(file)
    return UserService(db).update_avatar(current_user, path)


@user_router.delete("/avatar", response_model=FullProfileResponse)
def delete_avatar(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserService(db).delete_avatar(current_user)
