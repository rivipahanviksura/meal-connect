
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models.user import UserRole, AccountStatus


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=25)


class RegistrationRequest(UserCreate):
    account_type: Literal["business", "ngo"]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    role: UserRole
    account_status: AccountStatus


class RegistrationResponse(BaseModel):
    data: UserResponse


class LoginUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: EmailStr
    role: Literal["admin", "business_staff", "ngo_staff"]


class LoginResponse(BaseModel):
    class Data(BaseModel):
        access_token: str
        token_type: Literal["bearer"] = "bearer"
        expires_in: int = Field(gt=0)
        user: LoginUserSummary

    data: Data
