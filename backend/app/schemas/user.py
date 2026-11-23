from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.db.models.user import UserRole, AccountStatus
from app.schemas.common import DatabaseText, reject_null_character


AccountName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(reject_null_character),
]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: AccountName
    last_name: AccountName
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: DatabaseText | None = Field(default=None, max_length=25)


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
