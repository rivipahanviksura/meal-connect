
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# backend directory
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Optional until database and authentication are implemented.
    # Each feature must validate its required configuration before use.
    database_url: SecretStr | None = None
    secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
