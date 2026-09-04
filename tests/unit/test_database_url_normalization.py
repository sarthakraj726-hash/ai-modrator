"""Unit tests for canonical database URL normalization and credential sanitization."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database_url import normalize_database_url, sanitize_database_url


def test_normalize_postgresql_prefix():
    """Verify standard postgresql:// converts to postgresql+asyncpg://."""
    raw_url = "postgresql://myuser:mypassword@db.railway.internal:5432/railway"
    normalized = normalize_database_url(raw_url)
    assert normalized == "postgresql+asyncpg://myuser:mypassword@db.railway.internal:5432/railway"


def test_normalize_postgres_prefix():
    """Verify legacy postgres:// converts to postgresql+asyncpg://."""
    raw_url = "postgres://myuser:mypassword@db.railway.internal:5432/railway"
    normalized = normalize_database_url(raw_url)
    assert normalized == "postgresql+asyncpg://myuser:mypassword@db.railway.internal:5432/railway"


def test_normalize_asyncpg_prefix_preserved():
    """Verify existing postgresql+asyncpg:// remains untouched."""
    raw_url = "postgresql+asyncpg://myuser:mypassword@db.railway.internal:5432/railway?ssl=require"
    normalized = normalize_database_url(raw_url)
    assert normalized == raw_url


def test_normalize_psycopg2_prefix_safely_remapped():
    """Verify postgresql+psycopg2:// is safely remapped to postgresql+asyncpg://."""
    raw_url = "postgresql+psycopg2://myuser:mypassword@db.railway.internal:5432/railway"
    normalized = normalize_database_url(raw_url)
    assert normalized == "postgresql+asyncpg://myuser:mypassword@db.railway.internal:5432/railway"


def test_normalize_sqlite_urls():
    """Verify sqlite+aiosqlite:// is preserved and plain sqlite:// gets async driver."""
    assert (
        normalize_database_url("sqlite+aiosqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"
    )
    assert normalize_database_url("sqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"


def test_normalize_preserves_query_parameters_and_credentials():
    """Verify complex connection parameters (tokens, SSL options, custom ports) are preserved intact."""
    raw_url = "postgresql://app_user:complex%23pass@10.0.1.5:6543/goddess_db?ssl=prefer&application_name=modrator"
    normalized = normalize_database_url(raw_url)
    assert (
        normalized
        == "postgresql+asyncpg://app_user:complex%23pass@10.0.1.5:6543/goddess_db?ssl=prefer&application_name=modrator"
    )


def test_unsupported_scheme_rejected_safely():
    """Verify unsupported schemes fail with a clear exception and no credential leak."""
    with pytest.raises(ValueError) as excinfo:
        normalize_database_url("mysql://user:supersecretpass@localhost:3306/db")
    assert "Unsupported database scheme 'mysql'" in str(excinfo.value)
    assert "supersecretpass" not in str(excinfo.value)


def test_production_environment_enforces_postgresql_asyncpg():
    """In production, SQLite or non-asyncpg URLs are rejected immediately."""
    with pytest.raises(ValueError) as excinfo:
        normalize_database_url("sqlite+aiosqlite:///./dev.db", app_env="production")
    assert "Production DATABASE_URL must use an async PostgreSQL driver" in str(excinfo.value)

    # Valid PostgreSQL URL passes in production
    valid_prod = normalize_database_url(
        "postgres://user:pass@host:5432/prod_db", app_env="production"
    )
    assert valid_prod.startswith("postgresql+asyncpg://")


def test_sanitize_database_url_masks_password():
    """Verify passwords are redacted from log representations."""
    url = "postgresql+asyncpg://moderator:VerySecret123@postgres.railway.internal:5432/prod_db"
    sanitized = sanitize_database_url(url)
    assert "VerySecret123" not in sanitized
    assert "moderator:***@" in sanitized
    assert "postgres.railway.internal:5432/prod_db" in sanitized


def test_create_async_engine_uses_asyncpg_dialect():
    """Verify create_async_engine successfully initializes asyncpg dialect without requiring psycopg2."""
    normalized_url = normalize_database_url("postgresql://mockuser:mockpass@localhost:5432/mockdb")
    engine = create_async_engine(normalized_url)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "asyncpg"
    # Dispose without establishing connection
    engine.sync_engine.dispose()
