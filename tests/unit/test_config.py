"""Unit tests for configuration system."""

from app.core.config import Settings


def test_settings_defaults():
    settings = Settings()
    assert settings.APP_NAME == "goddess-ai-modrator"
    assert settings.YOUTUBE_QUOTA_DAILY_LIMIT == 40000
    assert settings.LOG_LEVEL == "INFO"


def test_settings_log_level_validation():
    s1 = Settings(LOG_LEVEL="debug")
    assert s1.LOG_LEVEL == "DEBUG"

    s2 = Settings(LOG_LEVEL="invalid_level")
    assert s2.LOG_LEVEL == "INFO"


def test_youtube_api_keys_property():
    s = Settings(
        YOUTUBE_API_KEY_1="key_1",
        YOUTUBE_API_KEY_2="",
        YOUTUBE_API_KEY_3="key_3",
    )
    keys = s.youtube_api_keys
    assert keys == ["key_1", "key_3"]
