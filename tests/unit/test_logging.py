"""Unit tests for structured logging and secret redaction."""

import json
import logging

from app.core.logging import (
    JSONLogFormatter,
    correlation_id_ctx,
    redact_secrets,
)


def test_secret_redactor():
    secret_text = "Connecting with api_key=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6 and password=supersecret"
    sanitized = redact_secrets(secret_text)
    assert "AIzaSy" not in sanitized or "[REDACTED" in sanitized
    assert "supersecret" not in sanitized


def test_json_log_formatter():
    formatter = JSONLogFormatter(service_name="test-service")
    correlation_id_ctx.set("test-corr-123")

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message with key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["service"] == "test-service"
    assert parsed["level"] == "INFO"
    assert parsed["correlation_id"] == "test-corr-123"
    assert "AIzaSy" not in parsed["message"]
