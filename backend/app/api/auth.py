from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import get_user_by_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


def create_user_record(
    db: Session,
    user_data: UserCreate,
    hashed_password: str
):
    new_user = User(
        name=user_data.name,
        email=str(user_data.email).lower(),
        password_hash=hashed_password,
        role=user_data.role,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account identifier already exists"
        )

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):

    allowed_roles = {"RESTAURANT", "NGO", "VOLUNTEER"}

    if user_data.role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="Invalid registration role"
        )


    existing_user = get_user_by_email(
        db,
        str(user_data.email)
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )


    raise HTTPException(
        status_code=503,
        detail="Registration temporarily unavailable: password hashing integration pending"
    )