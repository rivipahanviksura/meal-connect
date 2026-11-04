
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def get_engine():
    if settings.database_url is None:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    database_url = settings.database_url.get_secret_value()

    if "YOUR_DB_USER" in database_url or "YOUR_DB_PASSWORD" in database_url:
        raise RuntimeError(
            "Replace the DATABASE_URL placeholders in backend/.env."
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def get_session_factory():
    engine = get_engine()

    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
