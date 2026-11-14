"""User persistence against the MEAL-213 model; hashing belongs to MEAL-176."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models.user import AccountStatus, User, UserRole
from app.schemas.user import RegistrationRequest


class DuplicateEmailError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))


def create_user_record(db: Session, user_data: RegistrationRequest, hashed_password: str) -> User:
    """Persist a hash supplied by the hashing integration, never the raw password."""
    if not hashed_password or hashed_password == user_data.password:
        raise ValueError("A password hash is required")
    user = User(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        email=normalize_email(str(user_data.email)),
        phone=user_data.phone,
        password_hash=hashed_password,
        role={"business": UserRole.business_staff, "ngo": UserRole.ngo_staff}[user_data.account_type],
        account_status=AccountStatus.active,
    )
    try:
        if get_user_by_email(db, str(user_data.email)) is not None:
            raise DuplicateEmailError()
        db.add(user)
        db.flush()
        db.refresh(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Only the email unique constraint is an email conflict.
        original = exc.orig
        constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
        if constraint == "users_email_key" or "UNIQUE constraint failed: users.email" in str(original):
            raise DuplicateEmailError() from None
        raise
    except (SQLAlchemyError, DuplicateEmailError):
        db.rollback()
        raise
    return user
