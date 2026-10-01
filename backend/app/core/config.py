from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str = Field(min_length=1)
    jwt_secret: str = Field(min_length=1)
    cors_origins: str = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings(_env_file=ROOT_DIR / ".env")