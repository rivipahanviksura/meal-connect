from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    TokenConfigurationError,
    create_access_token,
    hash_password,
)
from app.db.session import get_db
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    LoginUserSummary,
    RegistrationRequest,
    RegistrationResponse,
)
from app.services.auth import (
    InactiveAccountError,
    InvalidCredentialsError,
    authenticate_user,
)
from app.services.user_service import DuplicateEmailError, create_user_record

router = APIRouter(prefix="/auth", tags=["Authentication"])


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={
        "error": {"code": code, "message": message, "fields": []},
    })


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register_user(
    user_data: RegistrationRequest,
    db: Session = Depends(get_db),
):
    hashed_password = hash_password(user_data.password)
    try:
        user = create_user_record(db, user_data, hashed_password)
    except DuplicateEmailError:
        return error_response(409, "ALREADY_EXISTS", "Email already registered")
    except SQLAlchemyError:
        return error_response(500, "INTERNAL_ERROR", "Unable to create account")
    return {"data": user}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, payload.email, payload.password)
        access_token = create_access_token(user.user_id)
    except InvalidCredentialsError:
        return error_response(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    except InactiveAccountError:
        return error_response(403, "ACCOUNT_INACTIVE", "This account is not active.")
    except TokenConfigurationError:
        return error_response(503, "AUTH_UNAVAILABLE", "Login temporarily unavailable.")
    except SQLAlchemyError:
        return error_response(500, "INTERNAL_ERROR", "Unable to sign in.")
    return LoginResponse(
        data=LoginResponse.Data(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=LoginUserSummary.model_validate(user),
        )
    )
