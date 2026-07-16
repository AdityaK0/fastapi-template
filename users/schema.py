from datetime import datetime
from pydantic import Field, BaseModel, EmailStr


# ------------------------------------------------------------------
# Request schemas
# ------------------------------------------------------------------

class CreateUser(BaseModel):
    username: str = Field(..., min_length=3, max_length=70)
    fullname: str = Field(..., min_length=2)
    email: EmailStr
    phone_number: str | None = Field(None, min_length=10, max_length=15)
    password: str = Field(..., min_length=6, max_length=70)


class LoginSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=70)


class UpdateProfileSchema(BaseModel):
    fullname: str | None = Field(None, min_length=2)
    phone_number: str | None = Field(None, min_length=10, max_length=15)


class ChangePasswordSchema(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6, max_length=70)


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------

class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    username: str
    fullname: str
    email: str
    phone_number: str | None
    is_active: bool
    created_at: datetime
    roles: list[RoleResponse] = []

    model_config = {"from_attributes": True}


class ProfileUpdateSchema(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    username: str | None = Field(None, min_length=3, max_length=50)
    phone_number: str | None = Field(None, min_length=10, max_length=15)
    bio: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=100)


class FullProfileResponse(BaseModel):
    id: int
    username: str
    fullname: str
    email: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    bio: str | None
    website: str | None
    location: str | None
    phone_number: str | None
    avatar_path: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None
    roles: list[RoleResponse] = []

    model_config = {"from_attributes": True}
