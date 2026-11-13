
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.core.security import create_access_token, verify_and_update
from app.db.models.user import User, AccountStatus


def login_user(db: Session, email: str, password: str) -> tuple[str, User]:
    statement = select(User).where(User.email == email)
    user = db.scalar(statement)


    if user is None:
        raise APIException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )

    password_valid, updated_hash = verify_and_update(
        password,
        user.password_hash,
    )

    if not password_valid:
        raise APIException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
        )

    if user.account_status != AccountStatus.active:
        raise APIException(
            status_code=403,
            code="ACCOUNT_INACTIVE",
            message="This account is not active.",
        )


    if updated_hash is not None:
        user.password_hash = updated_hash
        db.commit()

    access_token = create_access_token(user.user_id)

    return access_token, user
