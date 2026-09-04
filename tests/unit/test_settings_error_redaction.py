"""Unit tests verifying that Pydantic settings validation errors never leak input values or credentials."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_validation_error_redacts_input_value_in_production(monkeypatch):
    """
    Verify that with hide_input_in_errors=True, Pydantic's ValidationError:
    1. Never contains 'input_value='
    2. Never exposes sensitive database passwords
    3. Never exposes sensitive Redis passwords
    4. Never exposes sensitive usernames
    5. Preserves the safe production security violation message
    """
    sensitive_db_pass = "SuperSecretDbPassword9988!"
    sensitive_redis_pass = "SuperSecretRedisPassword7766!"
    sensitive_user = "PrivateAdminUser5544"

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "dev-admin-secret-replace-in-production")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql://{sensitive_user}:{sensitive_db_pass}@containers-us-west-1.railway.app:5432/railway",
    )
    monkeypatch.setenv(
        "REDIS_URL",
        f"redis://default:{sensitive_redis_pass}@redis.railway.internal:6379/0",
    )
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    err_str = str(excinfo.value)

    # 1. Pydantic input_value parameter must not be present
    assert "input_value=" not in err_str

    # 2. Sensitive database password must not be exposed
    assert sensitive_db_pass not in err_str

    # 3. Sensitive Redis password must not be exposed
    assert sensitive_redis_pass not in err_str

    # 4. Sensitive username must not be exposed
    assert sensitive_user not in err_str

    # 5. Safe diagnostic message must be preserved
    assert (
        "Production security violation: ADMIN_SECRET must be set to a secure secret and cannot use development placeholders."
        in err_str
    )

    get_settings.cache_clear()


def test_settings_field_validation_error_redacts_raw_input(monkeypatch):
    """
    Verify that invalid field type inputs (e.g. string passed to integer field)
    do not leak the invalid input text into Pydantic's string representation.
    """
    leaked_token = "LeakableSecretValue999"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "FakeProductionSecretOnlyForTests_123!")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://prod_user:prod_pass@containers-us-west-1.railway.app:5432/railway",
    )
    # Pass non-integer to integer field
    monkeypatch.setenv("PORT", leaked_token)
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    err_str = str(excinfo.value)
    # When hide_input_in_errors=True is active, input_value is omitted entirely
    assert "input_value=" not in err_str
    assert leaked_token not in err_str

    get_settings.cache_clear()


def test_settings_database_url_validation_error_does_not_leak_credentials(monkeypatch):
    """Verify that an invalid production database scheme does not leak connection string credentials."""
    sensitive_db_pass = "CompromisedPass12345"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "FakeProductionSecretOnlyForTests_123!")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite://admin:{sensitive_db_pass}@localhost/prod.db",
    )
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    err_str = str(excinfo.value)
    assert "input_value=" not in err_str
    assert sensitive_db_pass not in err_str
    assert "Production DATABASE_URL must use an async PostgreSQL driver" in err_str

    get_settings.cache_clear()


def test_settings_custom_invalid_admin_secret_not_leaked_as_input_value(monkeypatch):
    """
    Verify that an invalid ADMIN_SECRET value, API keys, or OAuth secrets
    are not leaked as input_value= in ValidationError.
    """
    fake_api_key = "AIzaSyFakeKey987654321"
    fake_openrouter_key = "sk-or-v1-fake-token-998877"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_SECRET", "short_weak_123")
    monkeypatch.setenv("YOUTUBE_API_KEY_1", fake_api_key)
    monkeypatch.setenv("OPENROUTER_API_KEY", fake_openrouter_key)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.railway.internal:5432/prod")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    err_str = str(excinfo.value)
    assert "input_value=" not in err_str
    assert fake_api_key not in err_str
    assert fake_openrouter_key not in err_str
    assert "Production security violation: ADMIN_SECRET must be set" in err_str

    get_settings.cache_clear()
