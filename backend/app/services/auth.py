from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.models.user import AccountStatus, User, UserRole
from app.services.user_service import get_user_by_email

LOGIN_ROLES = {UserRole.admin, UserRole.business_staff, UserRole.ngo_staff}


class InvalidCredentialsError(Exception):
    pass


class InactiveAccountError(Exception):
    pass


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    if user.role not in LOGIN_ROLES:
        raise InvalidCredentialsError
    if user.account_status != AccountStatus.active:
        raise InactiveAccountError
    return user
