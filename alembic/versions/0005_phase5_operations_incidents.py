"""Phase 5 schema migration: incidents, creator_discord_configs, feature_flags, system_metric_snapshots.

Revision ID: 0005_phase5_operations_incidents
Revises: 0004_phase4_engagement_economy
Create Date: 2026-09-03 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0005_phase5_operations_incidents"
down_revision: Union[str, None] = "0004_phase4_engagement_economy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Incidents
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("incident_id", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=True),
        sa.Column("stream_session_id", sa.String(length=36), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column(
            "actions_taken",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_incident_id", "incidents", ["incident_id"], unique=True)
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_service", "incidents", ["service"])
    op.create_index("ix_incidents_creator_id", "incidents", ["creator_id"])
    op.create_index("ix_incidents_detected_at", "incidents", ["detected_at"])
    op.create_index("ix_incidents_status_severity", "incidents", ["status", "severity"])
    op.create_index("ix_incidents_service_status", "incidents", ["service", "status"])

    # 2. Creator Discord Configs
    op.create_table(
        "creator_discord_configs",
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("log_channel_id", sa.String(length=64), nullable=True),
        sa.Column("alert_channel_id", sa.String(length=64), nullable=True),
        sa.Column("summary_channel_id", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("creator_id"),
    )

    # 3. Feature Flags
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("creator_id", sa.String(length=36), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False, default="all"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])
    op.create_index("ix_feature_flags_creator_id", "feature_flags", ["creator_id"])
    op.create_index(
        "uq_feature_flags_key_creator_env",
        "feature_flags",
        ["key", "creator_id", "environment"],
        unique=True,
    )

    # 4. System Metric Snapshots
    op.create_table(
        "system_metric_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_streams", sa.Integer(), nullable=False, default=0),
        sa.Column("memory_mb", sa.Float(), nullable=False, default=0.0),
        sa.Column("cpu_percent", sa.Float(), nullable=False, default=0.0),
        sa.Column("queue_depth", sa.Integer(), nullable=False, default=0),
        sa.Column("quota_remaining", sa.Integer(), nullable=False, default=4000),
        sa.Column(
            "metrics",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_metric_snapshots_timestamp", "system_metric_snapshots", ["timestamp"])


def downgrade() -> None:
    op.drop_table("system_metric_snapshots")
    op.drop_table("feature_flags")
    op.drop_table("creator_discord_configs")
    op.drop_table("incidents")
