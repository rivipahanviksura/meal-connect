
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import LoginRequest, TokenResponse, UserResponse
from app.services.auth import login_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    access_token, user = login_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )
