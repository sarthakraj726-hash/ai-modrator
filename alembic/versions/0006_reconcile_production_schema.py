"""Reconcile production schema drift: incidents, moderation_reviews.creator_id, and full operational schema.

Revision ID: 0006_reconcile_production_schema
Revises: 0005_phase5_operations_incidents
Create Date: 2026-09-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0006_reconcile_production_schema"
down_revision: Union[str, None] = "0005_phase5_operations_incidents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    # Helper functions for idempotency
    def safe_add_col(table: str, col: sa.Column) -> None:
        current_cols = {c["name"] for c in insp.get_columns(table)}
        if col.name not in current_cols:
            op.add_column(table, col)

    def safe_idx(name: str, table: str, cols: list[str], unique: bool = False) -> None:
        current_idxs = {i["name"] for i in insp.get_indexes(table)}
        if name not in current_idxs:
            op.create_index(name, table, cols, unique=unique)

    # -------------------------------------------------------------------------
    # 1. creators (ensure default creator exists if empty)
    # -------------------------------------------------------------------------
    if "creators" in existing_tables:
        safe_add_col("creators", sa.Column("youtube_channel_id", sa.String(64), nullable=True))
        safe_add_col("creators", sa.Column("channel_name", sa.String(255), nullable=True))
        safe_add_col("creators", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")))

    # -------------------------------------------------------------------------
    # 2. moderation_reviews (ensure table & creator_id exist)
    # -------------------------------------------------------------------------
    if "moderation_reviews" not in existing_tables:
        op.create_table(
            "moderation_reviews",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("stream_session_id", sa.String(length=36), nullable=False),
            sa.Column("message_id", sa.String(length=128), nullable=False),
            sa.Column("author_channel_id", sa.String(length=128), nullable=False),
            sa.Column("author_display_name", sa.String(length=255), nullable=False),
            sa.Column("message_text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("risk_score", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("confidence", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("severity", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("recommended_action", sa.String(length=32), nullable=False, server_default="DELETE"),
            sa.Column("final_action", sa.String(length=32), nullable=True),
            sa.Column("reason_code", sa.String(length=64), nullable=False, server_default="MODERATION_FLAG"),
            sa.Column("reason", sa.Text(), nullable=False, server_default="Flagged for review"),
            sa.Column("language", sa.String(length=32), nullable=False, server_default="en"),
            sa.Column("context_summary", json_type, nullable=False, server_default="{}"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        # Table exists: reconcile missing columns
        safe_add_col("moderation_reviews", sa.Column("creator_id", sa.String(length=36), nullable=False, server_default="default"))
        safe_add_col("moderation_reviews", sa.Column("stream_session_id", sa.String(length=36), nullable=False, server_default=""))
        safe_add_col("moderation_reviews", sa.Column("message_id", sa.String(length=128), nullable=False, server_default=""))
        safe_add_col("moderation_reviews", sa.Column("author_channel_id", sa.String(length=128), nullable=False, server_default=""))
        safe_add_col("moderation_reviews", sa.Column("author_display_name", sa.String(length=255), nullable=False, server_default=""))
        safe_add_col("moderation_reviews", sa.Column("message_text", sa.Text(), nullable=False, server_default=""))
        safe_add_col("moderation_reviews", sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"))
        safe_add_col("moderation_reviews", sa.Column("risk_score", sa.Integer(), nullable=False, server_default="50"))
        safe_add_col("moderation_reviews", sa.Column("confidence", sa.Integer(), nullable=False, server_default="50"))
        safe_add_col("moderation_reviews", sa.Column("severity", sa.Integer(), nullable=False, server_default="50"))
        safe_add_col("moderation_reviews", sa.Column("recommended_action", sa.String(length=32), nullable=False, server_default="DELETE"))
        safe_add_col("moderation_reviews", sa.Column("final_action", sa.String(length=32), nullable=True))
        safe_add_col("moderation_reviews", sa.Column("reason_code", sa.String(length=64), nullable=False, server_default="MODERATION_FLAG"))
        safe_add_col("moderation_reviews", sa.Column("reason", sa.Text(), nullable=False, server_default="Flagged for review"))
        safe_add_col("moderation_reviews", sa.Column("language", sa.String(length=32), nullable=False, server_default="en"))
        safe_add_col("moderation_reviews", sa.Column("context_summary", json_type, nullable=False, server_default="{}"))
        safe_add_col("moderation_reviews", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        safe_add_col("moderation_reviews", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
        safe_add_col("moderation_reviews", sa.Column("resolved_by", sa.String(length=128), nullable=True))
        safe_add_col("moderation_reviews", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        safe_add_col("moderation_reviews", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    safe_idx("ix_moderation_reviews_creator_id", "moderation_reviews", ["creator_id"])
    safe_idx("ix_moderation_reviews_stream_session_id", "moderation_reviews", ["stream_session_id"])
    safe_idx("ix_moderation_reviews_message_id", "moderation_reviews", ["message_id"])
    safe_idx("ix_moderation_reviews_author_channel_id", "moderation_reviews", ["author_channel_id"])
    safe_idx("ix_moderation_reviews_status", "moderation_reviews", ["status"])
    safe_idx("ix_mod_reviews_creator_status", "moderation_reviews", ["creator_id", "status"])

    # -------------------------------------------------------------------------
    # 3. moderation_feedback
    # -------------------------------------------------------------------------
    if "moderation_feedback" not in existing_tables:
        op.create_table(
            "moderation_feedback",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("review_id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("moderator_id", sa.String(length=128), nullable=False),
            sa.Column("decision", sa.String(length=32), nullable=False),
            sa.Column("action_taken", sa.String(length=32), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["review_id"], ["moderation_reviews.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_moderation_feedback_review_id", "moderation_feedback", ["review_id"])
        safe_idx("ix_moderation_feedback_creator_id", "moderation_feedback", ["creator_id"])
        safe_idx("ix_mod_feedback_creator_decision", "moderation_feedback", ["creator_id", "decision"])

    # -------------------------------------------------------------------------
    # 4. incidents
    # -------------------------------------------------------------------------
    if "incidents" not in existing_tables:
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
            sa.Column("actions_taken", json_type, nullable=False, server_default="[]"),
            sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        safe_add_col("incidents", sa.Column("incident_id", sa.String(length=32), nullable=False, server_default="INC-000"))
        safe_add_col("incidents", sa.Column("severity", sa.String(length=16), nullable=False, server_default="LOW"))
        safe_add_col("incidents", sa.Column("status", sa.String(length=24), nullable=False, server_default="OPEN"))
        safe_add_col("incidents", sa.Column("service", sa.String(length=32), nullable=False, server_default="ai-modrator"))
        safe_add_col("incidents", sa.Column("creator_id", sa.String(length=36), nullable=True))
        safe_add_col("incidents", sa.Column("stream_session_id", sa.String(length=36), nullable=True))
        safe_add_col("incidents", sa.Column("summary", sa.Text(), nullable=False, server_default=""))
        safe_add_col("incidents", sa.Column("root_cause", sa.Text(), nullable=True))
        safe_add_col("incidents", sa.Column("resolution", sa.Text(), nullable=True))
        safe_add_col("incidents", sa.Column("actions_taken", json_type, nullable=False, server_default="[]"))
        safe_add_col("incidents", sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        safe_add_col("incidents", sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True))
        safe_add_col("incidents", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
        safe_add_col("incidents", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        safe_add_col("incidents", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    safe_idx("ix_incidents_incident_id", "incidents", ["incident_id"], unique=True)
    safe_idx("ix_incidents_severity", "incidents", ["severity"])
    safe_idx("ix_incidents_status", "incidents", ["status"])
    safe_idx("ix_incidents_service", "incidents", ["service"])
    safe_idx("ix_incidents_creator_id", "incidents", ["creator_id"])
    safe_idx("ix_incidents_detected_at", "incidents", ["detected_at"])
    safe_idx("ix_incidents_status_severity", "incidents", ["status", "severity"])

    # -------------------------------------------------------------------------
    # 5. creator_discord_configs
    # -------------------------------------------------------------------------
    if "creator_discord_configs" not in existing_tables:
        op.create_table(
            "creator_discord_configs",
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("log_channel_id", sa.String(length=64), nullable=True),
            sa.Column("alert_channel_id", sa.String(length=64), nullable=True),
            sa.Column("summary_channel_id", sa.String(length=64), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("creator_id"),
        )

    # -------------------------------------------------------------------------
    # 6. feature_flags
    # -------------------------------------------------------------------------
    if "feature_flags" not in existing_tables:
        op.create_table(
            "feature_flags",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("creator_id", sa.String(length=36), nullable=True),
            sa.Column("environment", sa.String(length=32), nullable=False, server_default="all"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_feature_flags_key", "feature_flags", ["key"])
        safe_idx("ix_feature_flags_creator_id", "feature_flags", ["creator_id"])

    # -------------------------------------------------------------------------
    # 7. system_metric_snapshots
    # -------------------------------------------------------------------------
    if "system_metric_snapshots" not in existing_tables:
        op.create_table(
            "system_metric_snapshots",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("active_streams", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("memory_mb", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("cpu_percent", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("queue_depth", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("quota_remaining", sa.Integer(), nullable=False, server_default="4000"),
            sa.Column("metrics", json_type, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_system_metric_snapshots_timestamp", "system_metric_snapshots", ["timestamp"])


def downgrade() -> None:
    pass
