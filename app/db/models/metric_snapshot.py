"""System metric snapshot database model for historical performance trends."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, generate_uuid


class SystemMetricSnapshot(Base, TimestampMixin):
    """
    Stores periodic health, quota, latency, and resource utilization metrics
    for developer dashboard visualization.
    """

    __tablename__ = "system_metric_snapshots"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
    )
    active_streams: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    memory_mb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    cpu_percent: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    queue_depth: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    quota_remaining: Mapped[int] = mapped_column(
        Integer,
        default=4000,
        nullable=False,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        default=dict,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemMetricSnapshot(timestamp='{self.timestamp}', active_streams={self.active_streams}, mem={self.memory_mb}MB)>"
