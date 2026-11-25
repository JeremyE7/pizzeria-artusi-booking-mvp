from __future__ import annotations

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


settings = Settings()
