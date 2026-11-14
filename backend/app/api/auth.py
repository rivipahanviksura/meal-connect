from collections.abc import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import RegistrationRequest, RegistrationResponse
from app.services.user_service import DuplicateEmailError, create_user_record

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_password_hasher() -> Callable[[str], str] | None:
    """Connect to the teammate's MEAL-176 utility when it is available."""
    try:
        from app.core.security import hash_password
    except ModuleNotFoundError as exc:
        if exc.name != "app.core.security":
            raise
        return None
    return hash_password


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={
        "error": {"code": code, "message": message, "fields": []},
    })


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register_user(
    user_data: RegistrationRequest,
    db: Session = Depends(get_db),
    hasher: Callable[[str], str] | None = Depends(get_password_hasher),
):
    if hasher is None:
        return error_response(503, "REGISTRATION_UNAVAILABLE",
                              "Registration temporarily unavailable: password hashing integration pending")
    hashed_password = hasher(user_data.password)
    try:
        user = create_user_record(db, user_data, hashed_password)
    except DuplicateEmailError:
        return error_response(409, "ALREADY_EXISTS", "Email already registered")
    except SQLAlchemyError:
        return error_response(500, "INTERNAL_ERROR", "Unable to create account")
    return {"data": user}
