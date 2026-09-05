"""Reconcile all missing core tables: stream_sessions, audit_events, economy, websub, etc.

Revision ID: 0008_reconcile_missing_core_tables
Revises: 0007_create_monitored_channels
Create Date: 2026-09-05 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0008_reconcile_missing_core_tables"
down_revision: Union[str, None] = "0007_create_monitored_channels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

    def safe_idx(name: str, table: str, cols: list[str], unique: bool = False) -> None:
        try:
            is_pg = bind.dialect.name == "postgresql"
            if is_pg:
                uniq_clause = "UNIQUE " if unique else ""
                col_clause = ", ".join(f'"{c}"' for c in cols)
                bind.execute(sa.text(f'CREATE {uniq_clause}INDEX IF NOT EXISTS "{name}" ON "{table}" ({col_clause});'))
            else:
                op.create_index(name, table, cols, unique=unique)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. creators (ensure table exists)
    # -------------------------------------------------------------------------
    if "creators" not in existing_tables:
        op.create_table(
            "creators",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("youtube_channel_id", sa.String(length=64), nullable=False),
            sa.Column("channel_name", sa.String(length=255), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_creators")),
        )
        safe_idx(op.f("ix_creators_youtube_channel_id"), "creators", ["youtube_channel_id"], unique=True)
        existing_tables.add("creators")

    # -------------------------------------------------------------------------
    # 2. stream_sessions
    # -------------------------------------------------------------------------
    if "stream_sessions" not in existing_tables:
        op.create_table(
            "stream_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("youtube_video_id", sa.String(length=64), nullable=False),
            sa.Column("youtube_live_chat_id", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="IDLE"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], name=op.f("fk_stream_sessions_creator_id_creators"), ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_sessions")),
        )
        safe_idx(op.f("ix_stream_sessions_creator_id"), "stream_sessions", ["creator_id"], unique=False)
        safe_idx(op.f("ix_stream_sessions_youtube_video_id"), "stream_sessions", ["youtube_video_id"], unique=False)
        safe_idx(op.f("ix_stream_sessions_status"), "stream_sessions", ["status"], unique=False)
        safe_idx("ix_stream_sessions_creator_status", "stream_sessions", ["creator_id", "status"], unique=False)
        safe_idx("ix_stream_sessions_video_status", "stream_sessions", ["youtube_video_id", "status"], unique=False)
        existing_tables.add("stream_sessions")

    # -------------------------------------------------------------------------
    # 3. audit_events
    # -------------------------------------------------------------------------
    if "audit_events" not in existing_tables:
        op.create_table(
            "audit_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=True),
            sa.Column("stream_session_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="SYSTEM"),
            sa.Column("actor_id", sa.String(length=128), nullable=True),
            sa.Column("payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], name=op.f("fk_audit_events_creator_id_creators"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], name=op.f("fk_audit_events_stream_session_id_stream_sessions"), ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
        )
        safe_idx(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
        safe_idx(op.f("ix_audit_events_creator_id"), "audit_events", ["creator_id"], unique=False)
        safe_idx(op.f("ix_audit_events_stream_session_id"), "audit_events", ["stream_session_id"], unique=False)
        safe_idx(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"], unique=False)
        safe_idx("ix_audit_events_type_created", "audit_events", ["event_type", "created_at"], unique=False)
        safe_idx("ix_audit_events_creator_type", "audit_events", ["creator_id", "event_type"], unique=False)
        existing_tables.add("audit_events")

    # -------------------------------------------------------------------------
    # 4. system_events
    # -------------------------------------------------------------------------
    if "system_events" not in existing_tables:
        op.create_table(
            "system_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="INFO"),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("service", sa.String(length=64), nullable=False, server_default="ai-modrator"),
            sa.Column("stream_session_id", sa.String(length=36), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("metadata_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_system_events")),
        )
        safe_idx(op.f("ix_system_events_severity"), "system_events", ["severity"], unique=False)
        safe_idx(op.f("ix_system_events_event_type"), "system_events", ["event_type"], unique=False)
        safe_idx(op.f("ix_system_events_service"), "system_events", ["service"], unique=False)
        safe_idx(op.f("ix_system_events_stream_session_id"), "system_events", ["stream_session_id"], unique=False)
        safe_idx(op.f("ix_system_events_created_at"), "system_events", ["created_at"], unique=False)
        safe_idx("ix_system_events_sev_created", "system_events", ["severity", "created_at"], unique=False)
        safe_idx("ix_system_events_type_created", "system_events", ["event_type", "created_at"], unique=False)
        existing_tables.add("system_events")

    # -------------------------------------------------------------------------
    # 5. youtube_websub_subscriptions
    # -------------------------------------------------------------------------
    if "youtube_websub_subscriptions" not in existing_tables:
        op.create_table(
            "youtube_websub_subscriptions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("channel_id", sa.String(length=64), nullable=False),
            sa.Column("topic_url", sa.String(length=512), nullable=False),
            sa.Column("callback_url", sa.String(length=512), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("lease_seconds", sa.Integer(), nullable=False, server_default="864000"),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_subscribed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_notification_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], name=op.f("fk_websub_creator_id_creators"), ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_websub_subscriptions")),
        )
        safe_idx(op.f("ix_youtube_websub_subscriptions_creator_id"), "youtube_websub_subscriptions", ["creator_id"], unique=False)
        safe_idx(op.f("ix_youtube_websub_subscriptions_channel_id"), "youtube_websub_subscriptions", ["channel_id"], unique=False)
        safe_idx(op.f("ix_youtube_websub_subscriptions_topic_url"), "youtube_websub_subscriptions", ["topic_url"], unique=False)
        safe_idx(op.f("ix_youtube_websub_subscriptions_status"), "youtube_websub_subscriptions", ["status"], unique=False)
        safe_idx("ix_websub_channel_status", "youtube_websub_subscriptions", ["channel_id", "status"], unique=False)
        safe_idx("ix_websub_lease_expiry", "youtube_websub_subscriptions", ["lease_expires_at"], unique=False)
        existing_tables.add("youtube_websub_subscriptions")

    # -------------------------------------------------------------------------
    # 6. youtube_discovery_events
    # -------------------------------------------------------------------------
    if "youtube_discovery_events" not in existing_tables:
        op.create_table(
            "youtube_discovery_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=True),
            sa.Column("channel_id", sa.String(length=64), nullable=False),
            sa.Column("video_id", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False, server_default="WEBSUB_NOTIFICATION"),
            sa.Column("source", sa.String(length=64), nullable=False, server_default="websub"),
            sa.Column("dedupe_hash", sa.String(length=64), nullable=False),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("payload", json_type, nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_discovery_events")),
        )
        safe_idx(op.f("ix_youtube_discovery_events_creator_id"), "youtube_discovery_events", ["creator_id"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_channel_id"), "youtube_discovery_events", ["channel_id"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_video_id"), "youtube_discovery_events", ["video_id"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_event_type"), "youtube_discovery_events", ["event_type"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_dedupe_hash"), "youtube_discovery_events", ["dedupe_hash"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_processed"), "youtube_discovery_events", ["processed"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_received_at"), "youtube_discovery_events", ["received_at"], unique=False)
        safe_idx("ix_discovery_dedupe_processed", "youtube_discovery_events", ["dedupe_hash", "processed"], unique=False)
        safe_idx("ix_discovery_video_processed", "youtube_discovery_events", ["video_id", "processed"], unique=False)
        existing_tables.add("youtube_discovery_events")

    # -------------------------------------------------------------------------
    # 7. youtube_checkpoints
    # -------------------------------------------------------------------------
    if "youtube_checkpoints" not in existing_tables:
        op.create_table(
            "youtube_checkpoints",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("stream_session_id", sa.String(length=36), nullable=False),
            sa.Column("last_next_page_token", sa.String(length=255), nullable=True),
            sa.Column("last_message_id", sa.String(length=128), nullable=True),
            sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_messages_ingested", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], name=op.f("fk_checkpoints_session_id_stream_sessions"), ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_checkpoints")),
            sa.UniqueConstraint("stream_session_id", name="uq_youtube_checkpoints_stream_session_id"),
        )
        safe_idx(op.f("ix_youtube_checkpoints_stream_session_id"), "youtube_checkpoints", ["stream_session_id"], unique=True)
        existing_tables.add("youtube_checkpoints")

    # -------------------------------------------------------------------------
    # 8. viewer_trust_profiles
    # -------------------------------------------------------------------------
    if "viewer_trust_profiles" not in existing_tables:
        op.create_table(
            "viewer_trust_profiles",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("viewer_channel_id", sa.String(length=128), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("trust_score", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("messages_seen", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("positive_interactions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("timeout_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hide_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_greeting_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "viewer_channel_id", name="uq_viewer_trust_creator_channel"),
        )
        safe_idx(op.f("ix_viewer_trust_profiles_creator_id"), "viewer_trust_profiles", ["creator_id"])
        safe_idx(op.f("ix_viewer_trust_profiles_viewer_channel_id"), "viewer_trust_profiles", ["viewer_channel_id"])
        safe_idx("ix_viewer_trust_score", "viewer_trust_profiles", ["creator_id", "trust_score"])
        existing_tables.add("viewer_trust_profiles")

    # -------------------------------------------------------------------------
    # 9. ai_usage_records
    # -------------------------------------------------------------------------
    if "ai_usage_records" not in existing_tables:
        op.create_table(
            "ai_usage_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=True),
            sa.Column("stream_session_id", sa.String(length=36), nullable=True),
            sa.Column("provider", sa.String(length=64), nullable=False, server_default="openrouter"),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("task_type", sa.String(length=64), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx(op.f("ix_ai_usage_records_creator_id"), "ai_usage_records", ["creator_id"])
        safe_idx(op.f("ix_ai_usage_records_stream_session_id"), "ai_usage_records", ["stream_session_id"])
        safe_idx(op.f("ix_ai_usage_records_model"), "ai_usage_records", ["model"])
        safe_idx(op.f("ix_ai_usage_records_task_type"), "ai_usage_records", ["task_type"])
        safe_idx("ix_ai_usage_creator_task", "ai_usage_records", ["creator_id", "task_type"])
        safe_idx("ix_ai_usage_created_at", "ai_usage_records", ["created_at"])
        existing_tables.add("ai_usage_records")

    # -------------------------------------------------------------------------
    # 10. creator_ai_settings
    # -------------------------------------------------------------------------
    if "creator_ai_settings" not in existing_tables:
        op.create_table(
            "creator_ai_settings",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("persona_type", sa.String(length=32), nullable=False, server_default="CO_HOST"),
            sa.Column("persona_sliders", json_type, nullable=False),
            sa.Column("custom_persona_prompt", sa.Text(), nullable=True),
            sa.Column("moderation_strictness", sa.String(length=32), nullable=False, server_default="BALANCED"),
            sa.Column("moderation_mode", sa.String(length=32), nullable=False, server_default="ACTIVE"),
            sa.Column("auto_moderation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("hitl_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("ai_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("greeting_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("farewell_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("quiet_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("max_ai_messages_per_minute", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("ai_daily_budget", sa.Integer(), nullable=False, server_default="1000"),
            sa.Column("custom_rules", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", name="uq_creator_ai_settings_creator_id"),
        )
        safe_idx(op.f("ix_creator_ai_settings_creator_id"), "creator_ai_settings", ["creator_id"], unique=True)
        existing_tables.add("creator_ai_settings")

    # -------------------------------------------------------------------------
    # 11. custom_commands & command_aliases
    # -------------------------------------------------------------------------
    if "custom_commands" not in existing_tables:
        op.create_table(
            "custom_commands",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("response", sa.Text(), nullable=False),
            sa.Column("min_role", sa.String(length=32), nullable=False, server_default="VIEWER"),
            sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "name", name="uq_custom_commands_creator_name"),
        )
        safe_idx("ix_custom_commands_creator_id", "custom_commands", ["creator_id"])
        safe_idx("ix_custom_commands_creator_name", "custom_commands", ["creator_id", "name"])
        existing_tables.add("custom_commands")

    if "command_aliases" not in existing_tables:
        op.create_table(
            "command_aliases",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("alias", sa.String(length=64), nullable=False),
            sa.Column("target_command_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_command_id"], ["custom_commands.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "alias", name="uq_command_aliases_creator_alias"),
        )
        safe_idx("ix_command_aliases_creator_id", "command_aliases", ["creator_id"])
        safe_idx("ix_command_aliases_creator_alias", "command_aliases", ["creator_id", "alias"])
        existing_tables.add("command_aliases")

    # -------------------------------------------------------------------------
    # 12. viewer_engagements
    # -------------------------------------------------------------------------
    if "viewer_engagements" not in existing_tables:
        op.create_table(
            "viewer_engagements",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("viewer_channel_id", sa.String(length=128), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("total_xp", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("messages_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("games_played", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("games_won", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("store_purchases", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_xp_awarded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "viewer_channel_id", name="uq_viewer_engagement_creator_viewer"),
        )
        safe_idx("ix_viewer_engagements_creator_id", "viewer_engagements", ["creator_id"])
        safe_idx("ix_viewer_engagements_viewer_channel_id", "viewer_engagements", ["viewer_channel_id"])
        safe_idx("ix_viewer_engagement_xp", "viewer_engagements", ["creator_id", "total_xp"])
        safe_idx("ix_viewer_engagement_level", "viewer_engagements", ["creator_id", "level"])
        existing_tables.add("viewer_engagements")

    # -------------------------------------------------------------------------
    # 13. economy_accounts, economy_transactions, economy_ledger_entries
    # -------------------------------------------------------------------------
    if "economy_accounts" not in existing_tables:
        op.create_table(
            "economy_accounts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("viewer_channel_id", sa.String(length=128), nullable=True),
            sa.Column("account_type", sa.String(length=32), nullable=False, server_default="VIEWER"),
            sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "viewer_channel_id", "account_type", name="uq_economy_account_creator_viewer_type"),
        )
        safe_idx("ix_economy_accounts_creator_id", "economy_accounts", ["creator_id"])
        safe_idx("ix_economy_accounts_viewer_channel_id", "economy_accounts", ["viewer_channel_id"])
        safe_idx("ix_economy_account_creator_balance", "economy_accounts", ["creator_id", "balance"])
        existing_tables.add("economy_accounts")

    if "economy_transactions" not in existing_tables:
        op.create_table(
            "economy_transactions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("transaction_type", sa.String(length=32), nullable=False),
            sa.Column("reference_type", sa.String(length=64), nullable=True),
            sa.Column("reference_id", sa.String(length=128), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "idempotency_key", name="uq_economy_tx_creator_idempotency"),
        )
        safe_idx("ix_economy_transactions_creator_id", "economy_transactions", ["creator_id"])
        safe_idx("ix_economy_tx_creator_created", "economy_transactions", ["creator_id", "created_at"])
        existing_tables.add("economy_transactions")

    if "economy_ledger_entries" not in existing_tables:
        op.create_table(
            "economy_ledger_entries",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("transaction_id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=36), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["account_id"], ["economy_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["transaction_id"], ["economy_transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_economy_ledger_entries_transaction_id", "economy_ledger_entries", ["transaction_id"])
        safe_idx("ix_economy_ledger_entries_account_id", "economy_ledger_entries", ["account_id"])
        safe_idx("ix_economy_ledger_account_created", "economy_ledger_entries", ["account_id", "created_at"])
        existing_tables.add("economy_ledger_entries")

    # -------------------------------------------------------------------------
    # 14. store_items & viewer_inventories
    # -------------------------------------------------------------------------
    if "store_items" not in existing_tables:
        op.create_table(
            "store_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("price", sa.Integer(), nullable=False),
            sa.Column("stock", sa.Integer(), nullable=False, server_default="-1"),
            sa.Column("max_per_user", sa.Integer(), nullable=False, server_default="-1"),
            sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "name", name="uq_store_items_creator_name"),
        )
        safe_idx("ix_store_items_creator_id", "store_items", ["creator_id"])
        safe_idx("ix_store_items_creator_enabled", "store_items", ["creator_id", "enabled"])
        existing_tables.add("store_items")

    if "viewer_inventories" not in existing_tables:
        op.create_table(
            "viewer_inventories",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("viewer_channel_id", sa.String(length=128), nullable=False),
            sa.Column("item_id", sa.String(length=36), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("first_acquired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_acquired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["store_items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "viewer_channel_id", "item_id", name="uq_viewer_inventory_creator_viewer_item"),
        )
        safe_idx("ix_viewer_inventories_creator_id", "viewer_inventories", ["creator_id"])
        safe_idx("ix_viewer_inventories_viewer_channel_id", "viewer_inventories", ["viewer_channel_id"])
        safe_idx("ix_viewer_inventories_item_id", "viewer_inventories", ["item_id"])
        existing_tables.add("viewer_inventories")

    # -------------------------------------------------------------------------
    # 15. mini_game_sessions
    # -------------------------------------------------------------------------
    if "mini_game_sessions" not in existing_tables:
        op.create_table(
            "mini_game_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("stream_session_id", sa.String(length=36), nullable=False),
            sa.Column("game_type", sa.String(length=32), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False, server_default="ACTIVE"),
            sa.Column("prompt_text", sa.String(length=255), nullable=False),
            sa.Column("solution_data", json_type, nullable=False),
            sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="25"),
            sa.Column("winner_channel_id", sa.String(length=128), nullable=True),
            sa.Column("winner_display_name", sa.String(length=255), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_mini_games_creator_state", "mini_game_sessions", ["creator_id", "state"])
        safe_idx("ix_mini_games_session_state", "mini_game_sessions", ["stream_session_id", "state"])
        safe_idx("ix_mini_game_sessions_creator_id", "mini_game_sessions", ["creator_id"])
        safe_idx("ix_mini_game_sessions_stream_session_id", "mini_game_sessions", ["stream_session_id"])
        existing_tables.add("mini_game_sessions")


def downgrade() -> None:
    pass
