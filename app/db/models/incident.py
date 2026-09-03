"""Production incident database model."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, generate_uuid


class Incident(Base, TimestampMixin):
    """
    Tracks operational incidents, provider outages, ledger integrity failures,
    and automatic or manual resolutions.
    """

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    incident_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        index=True,
        nullable=False,  # LOW, MEDIUM, HIGH, CRITICAL
    )
    status: Mapped[str] = mapped_column(
        String(24),
        index=True,
        default="OPEN",
        nullable=False,  # OPEN, INVESTIGATING, MITIGATED, RESOLVED, CLOSED
    )
    service: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,  # YOUTUBE, OPENROUTER, REDIS, POSTGRES, DISCORD, ECONOMY, WORKER, SYSTEM
    )
    creator_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("creators.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    stream_session_id: Mapped[str | None] = mapped_column(
        String(36),
        index=True,
        nullable=True,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    resolution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    actions_taken: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=list,
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
    )
    mitigated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    creator = relationship("Creator")

    __table_args__ = (
        Index("ix_incidents_status_severity", "status", "severity"),
        Index("ix_incidents_service_status", "service", "status"),
    )

    def __repr__(self) -> str:
        return f"<Incident(id={self.incident_id}, severity='{self.severity}', status='{self.status}', service='{self.service}')>"
