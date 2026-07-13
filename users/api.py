from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from database import get_db
from .schema import CreateUser, LoginSchema, UpdateProfileSchema, ChangePasswordSchema, UserResponse
from .service import UserService
from .dependencies import get_current_user, require_permission
from .permissions import USER_UPDATE, USER_DEACTIVATE, ROLE_ASSIGN

user_router = APIRouter(prefix="/users", tags=["Users"])

SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@user_router.post("/register")
def register(data: CreateUser, db: Session = Depends(get_db)):
    user = UserService(db).register(data)
    return {"message": "User registered successfully", "id": user.id, "username": user.username}


@user_router.post("/login")
def login(command: LoginSchema, request: Request, response: Response, db: Session = Depends(get_db)):
    session_token = UserService(db).login(command, request)
    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        secure=False,  # True in production (HTTPS)
        samesite="lax",
        max_age=SESSION_COOKIE_MAX_AGE,
    )
    return {"message": "Login successful"}


@user_router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_id")
    if session_token:
        UserService(db).logout(session_token)
    response.delete_cookie("session_id")
    return {"message": "Logged out successfully"}


@user_router.post("/logout-all")
def logout_all(response: Response, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    UserService(db).logout_all_devices(current_user.id)
    response.delete_cookie("session_id")
    return {"message": "Logged out from all devices"}


@user_router.get("/profile", response_model=UserResponse)
def profile(current_user=Depends(get_current_user)):
    return current_user


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
