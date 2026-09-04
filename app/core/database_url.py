"""Canonical database URL normalization and credential sanitization for SQLAlchemy AsyncEngine."""

import re

from app.core.logging import get_logger

logger = get_logger("app.core.database_url")


def sanitize_connection_url(url: str) -> str:
    """
    Mask credentials in any database, Redis, or HTTP connection string.
    Supports both user:password@host and :password@host formats.
    e.g. redis://default:secret@host:6379/0 -> redis://default:***@host:6379/0
    e.g. redis://:secret@host:6379/0        -> redis://:***@host:6379/0
    """
    if not url:
        return ""
    try:
        # Regex replacement for password in URI format: scheme://[user]:pass@host
        return re.sub(r"://([^:@]*):([^@]+)@", r"://\1:***@", str(url))
    except Exception:
        return "[REDACTED_URL]"


def sanitize_database_url(url: str) -> str:
    """Mask credentials in database connection string for safe logging."""
    return sanitize_connection_url(url)


def sanitize_redis_url(url: str) -> str:
    """Mask credentials in Redis connection string for safe logging."""
    return sanitize_connection_url(url)


def normalize_database_url(url: str, app_env: str = "development") -> str:
    """
    Normalize DATABASE_URL to guarantee compatibility with SQLAlchemy AsyncEngine.

    Conversions:
    - postgres://...          -> postgresql+asyncpg://...
    - postgresql://...        -> postgresql+asyncpg://...
    - postgresql+psycopg2://  -> postgresql+asyncpg://... (safely remap to asyncpg)
    - postgresql+asyncpg://   -> preserved
    - sqlite:///...           -> sqlite+aiosqlite:///...
    - sqlite+aiosqlite://     -> preserved

    Enforces that production environments require a valid async PostgreSQL driver.
    Never exposes raw passwords in exceptions or logs.
    """
    if not url or not url.strip():
        raise ValueError("DATABASE_URL must not be empty.")

    cleaned_url = url.strip()

    # Determine scheme prefix
    if "://" not in cleaned_url:
        raise ValueError(
            f"Invalid DATABASE_URL format: missing scheme delimiter '://' in {sanitize_database_url(cleaned_url)}"
        )

    scheme, rest = cleaned_url.split("://", 1)
    scheme_lower = scheme.lower()

    if scheme_lower == "postgres":
        normalized = f"postgresql+asyncpg://{rest}"
    elif scheme_lower == "postgresql":
        normalized = f"postgresql+asyncpg://{rest}"
    elif scheme_lower == "postgresql+psycopg2":
        logger.warning(
            "Detected 'postgresql+psycopg2://' driver. Remapping to 'postgresql+asyncpg://' for AsyncEngine compatibility."
        )
        normalized = f"postgresql+asyncpg://{rest}"
    elif scheme_lower == "postgresql+asyncpg":
        normalized = cleaned_url
    elif scheme_lower == "sqlite":
        normalized = f"sqlite+aiosqlite://{rest}"
    elif scheme_lower == "sqlite+aiosqlite":
        normalized = cleaned_url
    else:
        raise ValueError(
            f"Unsupported database scheme '{scheme}' in DATABASE_URL. "
            "Goddess AI requires an async driver: 'postgresql+asyncpg://' or 'sqlite+aiosqlite://'."
        )

    # Fail-fast validation for production
    if app_env.lower() == "production":
        if not normalized.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "Production DATABASE_URL must use an async PostgreSQL driver compatible "
                "with SQLAlchemy AsyncEngine (postgresql+asyncpg://)."
            )

    return normalized
