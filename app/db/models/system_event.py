"""SystemEvent database model."""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, generate_uuid, utc_now


class SystemSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        default=SystemSeverity.INFO.value,
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    service: Mapped[str] = mapped_column(
        String(64),
        default="ai-modrator",
        index=True,
        nullable=False,
    )
    stream_session_id: Mapped[str | None] = mapped_column(
        String(36),
        index=True,
        nullable=True,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_system_events_sev_created", "severity", "created_at"),
        Index("ix_system_events_type_created", "event_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SystemEvent(id={self.id}, severity='{self.severity}', type='{self.event_type}')>"
