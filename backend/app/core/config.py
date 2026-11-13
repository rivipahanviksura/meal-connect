
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Backend directory
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Database configuration
    database_url: SecretStr | None = None

    # JWT secret key
    secret_key: SecretStr | None = None

    # JWT configuration
    jwt_algorithm: str = "HS256"

    # Access token expiration time (30 minutes)
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
