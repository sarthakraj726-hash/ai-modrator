"""Centralized application settings using Pydantic Settings."""

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
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
    APP_SERVICE_MODE: Literal["unified", "api", "worker"] = "unified"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Continuous Health & Reliability
    HEALTH_CHECK_INTERVAL_SECONDS: int = Field(default=30, ge=5, le=300)
    HEALTH_CHECK_TIMEOUT_SECONDS: float = Field(default=5.0, ge=1.0, le=30.0)
    DISCORD_RETRY_QUEUE_MAX_SIZE: int = Field(default=1000, ge=50)

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

    # OpenRouter LLM Gateway & Model Routing
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "anthropic/claude-3.5-sonnet"
    OPENROUTER_MODEL_PRIMARY: str = "anthropic/claude-3.5-sonnet"
    OPENROUTER_MODEL_FAST: str = "meta-llama/llama-3.3-70b-instruct"
    OPENROUTER_MODEL_FALLBACK: str = "mistralai/mistral-large-2411"
    OPENROUTER_MODEL_REASONING: str = "deepseek/deepseek-r1"

    # AI Budget & Rate Limiting Controls
    AI_DAILY_REQUEST_LIMIT: int = Field(default=2000, ge=1)
    AI_PER_STREAM_REQUEST_LIMIT: int = Field(default=500, ge=1)
    AI_PER_USER_REQUEST_LIMIT: int = Field(default=20, ge=1)
    AI_MONTHLY_TOKEN_BUDGET: int = Field(default=1000000, ge=1)
    AI_MAX_REPLY_TOKENS: int = Field(default=100, ge=1)
    HONNEY_MAX_REPLY_CHARS: int = Field(default=200, ge=1)
    HONNEY_MAX_REPLY_TOKENS: int = Field(default=100, ge=1)
    HITL_REVIEW_TTL_SECONDS: int = Field(default=60, ge=10, le=600)

    # Discord Bot & Logging Integration (Future Observability)
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_DEV_CHANNEL_ID: str = ""

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def validate_app_env(cls, v: Any) -> str:
        import os

        env_var = os.environ.get("APP_ENV")
        if env_var and env_var.strip():
            clean = env_var.strip().lower()
            if clean in ("production", "prod"):
                return "production"
            if clean in ("testing", "test"):
                return "testing"
            if clean in ("development", "dev"):
                return "development"
            return clean

        # Auto-detect Railway production environment if APP_ENV not explicitly set
        railway_env = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get(
            "RAILWAY_ENVIRONMENT_NAME"
        )
        if railway_env and railway_env.lower() in ("production", "prod"):
            return "production"
        if os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_SERVICE_ID"):
            return "production"

        if isinstance(v, str) and v.strip():
            clean = v.strip().lower()
            if clean in ("production", "prod"):
                return "production"
            if clean in ("testing", "test"):
                return "testing"
            if clean in ("development", "dev"):
                return "development"
            return clean

        return "development"

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            return "INFO"
        return upper_v

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_db_url_field(cls, v: str) -> str:
        from app.core.database_url import normalize_database_url

        return normalize_database_url(v, app_env="development")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        from app.core.database_url import normalize_database_url

        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL, app_env=self.APP_ENV)

        if self.is_production:
            insecure_secrets = {
                "dev-admin-secret-replace-in-production",
                "change-this-to-a-secure-random-secret-in-production",
                "admin",
                "secret",
                "password",
            }
            if self.ADMIN_SECRET in insecure_secrets:
                raise ValueError(
                    "Production security violation: ADMIN_SECRET must be set to a secure secret and cannot use development placeholders."
                )

            if self.CORS_ORIGINS == ["*"]:
                self.CORS_ORIGINS = ["https://railway.app"]

        return self

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

    @property
    def is_api_service(self) -> bool:
        return self.APP_SERVICE_MODE in ("unified", "api")

    @property
    def is_worker_service(self) -> bool:
        return self.APP_SERVICE_MODE in ("unified", "worker")

    @property
    def is_unified_service(self) -> bool:
        return self.APP_SERVICE_MODE == "unified"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
