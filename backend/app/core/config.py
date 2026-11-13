
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# backend directory
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Optional until database and authentication are implemented.
    # Each feature must validate its required configuration before use.
    database_url: SecretStr | None = None
    secret_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
