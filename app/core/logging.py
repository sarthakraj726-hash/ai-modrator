"""Structured JSON logging with correlation IDs and secret redaction."""

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Context variables for distributed tracing and stream isolation
correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
creator_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "creator_id", default=None
)
stream_session_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "stream_session_id", default=None
)

# Regular expressions for identifying and redacting sensitive data
SENSITIVE_PATTERNS = [
    (
        re.compile(
            r"(api[_-]?key|secret|password|token|authorization|bearer)[\"':=\s]+([^\s\"',&]+)",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
    (re.compile(r"(AIzaSy[A-Za-z0-9_-]{25,40})"), "[REDACTED_YOUTUBE_KEY]"),
    (re.compile(r"(sk-or-v1-[a-zA-Z0-9]{30,80})"), "[REDACTED_OPENROUTER_KEY]"),
]


def redact_secrets(text: str) -> str:
    """Mask sensitive tokens, passwords, and API keys."""
    if not isinstance(text, str):
        return text
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class JSONLogFormatter(logging.Formatter):
    """Formats log records as structured JSON with contextual metadata."""

    def __init__(self, service_name: str = "ai-modrator"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        # Base log payload
        log_entry: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
            "correlation_id": correlation_id_ctx.get(),
            "creator_id": creator_id_ctx.get(),
            "stream_session_id": stream_session_id_ctx.get(),
        }

        # Include custom extra metadata if supplied
        if hasattr(record, "event") and record.event:  # type: ignore
            log_entry["event"] = record.event  # type: ignore
        if hasattr(record, "metadata") and isinstance(record.metadata, dict):  # type: ignore
            log_entry["metadata"] = {
                k: redact_secrets(str(v)) if isinstance(v, str) else v
                for k, v in record.metadata.items()  # type: ignore
            }

        # Include exception trace if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class ConsoleLogFormatter(logging.Formatter):
    """Human-readable console formatter for local development and testing."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S")
        corr = correlation_id_ctx.get()
        corr_tag = f" [{corr[:8]}]" if corr else ""
        session = stream_session_id_ctx.get()
        session_tag = f" [session:{session[:8]}]" if session else ""
        msg = redact_secrets(record.getMessage())
        return f"{timestamp} [{record.levelname:<7}] {record.name}{corr_tag}{session_tag}: {msg}"


def setup_logging(
    log_level: str = "INFO", app_env: str = "development", service_name: str = "ai-modrator"
) -> None:
    """Configure root and application loggers with appropriate formatters."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    if app_env == "production":
        stream_handler.setFormatter(JSONLogFormatter(service_name=service_name))
    else:
        stream_handler.setFormatter(ConsoleLogFormatter())

    root_logger.addHandler(stream_handler)

    # Suppress verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance configured for the application."""
    return logging.getLogger(name)
