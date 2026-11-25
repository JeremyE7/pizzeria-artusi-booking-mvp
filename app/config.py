from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/artusi"
    timezone: str = "Europe/Rome"
    slot_minutes: int = 30
    booking_duration_minutes: int = 90
    booking_horizon_days: int = 60

    # mock | openrouter
    llm_provider: str = "mock"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"

    # Optional "user:password" for /admin and booking APIs in public demos.
    demo_basic_auth: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        """Accept Render/Railway URLs that omit the psycopg driver."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+psycopg://" + value[len("postgres://") :]
            if value.startswith("postgresql://"):
                return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value


settings = Settings()
