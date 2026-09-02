"""Centralized application settings using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Environment
    APP_ENV: Literal["development", "production", "testing"] = "development"
    APP_NAME: str = "goddess-ai-modrator"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security & Admin Access
    ADMIN_SECRET: str = Field(
        default="dev-admin-secret-replace-in-production",
        description="Master secret for admin API authentication",
    )
    CORS_ORIGINS: list[str] = ["*"]

    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./ai_modrator.db",
        description="Async SQLAlchemy database connection string",
    )

    # Redis (Cache, Distributed Locks, Events)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # YouTube Data API v3 Key Pool
    YOUTUBE_API_KEY_1: str = ""
    YOUTUBE_API_KEY_2: str = ""
    YOUTUBE_API_KEY_3: str = ""

    # YouTube Daily Quota Hard Budget (Units per Day)
    YOUTUBE_QUOTA_DAILY_LIMIT: int = Field(
        default=4000,
        ge=1,
        description="Hard daily cap for YouTube Data API units",
    )

    # OpenRouter LLM Gateway (Future AI Provider)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "anthropic/claude-3.5-sonnet"

    # Discord Bot & Logging Integration (Future Observability)
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_DEV_CHANNEL_ID: str = ""

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            return "INFO"
        return upper_v

    @property
    def youtube_api_keys(self) -> list[str]:
        """Return non-empty YouTube API keys from the pool."""
        keys = [self.YOUTUBE_API_KEY_1, self.YOUTUBE_API_KEY_2, self.YOUTUBE_API_KEY_3]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == "testing"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
