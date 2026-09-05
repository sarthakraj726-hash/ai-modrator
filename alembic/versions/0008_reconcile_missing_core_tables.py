"""Reconcile all missing core tables: stream_sessions, audit_events, economy, websub, etc.

Revision ID: 0008_reconcile_missing_core_tables
Revises: 0007_create_monitored_channels
Create Date: 2026-09-05 14:50:00.000000

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
            current_idxs = {i["name"] for i in insp.get_indexes(table)}
            if name not in current_idxs:
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
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=True),
            sa.Column("stream_session_id", sa.String(length=36), nullable=True),
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
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("raw_payload", json_type, nullable=False),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_discovery_events")),
        )
        safe_idx(op.f("ix_youtube_discovery_events_channel_id"), "youtube_discovery_events", ["channel_id"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_video_id"), "youtube_discovery_events", ["video_id"], unique=False)
        safe_idx(op.f("ix_youtube_discovery_events_processed"), "youtube_discovery_events", ["processed"], unique=False)
        safe_idx("ix_discovery_channel_video", "youtube_discovery_events", ["channel_id", "video_id"], unique=False)
        existing_tables.add("youtube_discovery_events")

    # -------------------------------------------------------------------------
    # 7. youtube_checkpoints
    # -------------------------------------------------------------------------
    if "youtube_checkpoints" not in existing_tables:
        op.create_table(
            "youtube_checkpoints",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("stream_session_id", sa.String(length=36), nullable=False),
            sa.Column("live_chat_id", sa.String(length=128), nullable=False),
            sa.Column("page_token", sa.String(length=255), nullable=True),
            sa.Column("last_message_timestamp", sa.DateTime(timezone=True), nullable=True),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_checkpoints")),
        )
        safe_idx(op.f("ix_youtube_checkpoints_stream_session_id"), "youtube_checkpoints", ["stream_session_id"], unique=False)
        safe_idx(op.f("ix_youtube_checkpoints_live_chat_id"), "youtube_checkpoints", ["live_chat_id"], unique=False)
        existing_tables.add("youtube_checkpoints")

    # -------------------------------------------------------------------------
    # 8. viewer_trust_profiles
    # -------------------------------------------------------------------------
    if "viewer_trust_profiles" not in existing_tables:
        op.create_table(
            "viewer_trust_profiles",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("author_channel_id", sa.String(length=128), nullable=False),
            sa.Column("author_display_name", sa.String(length=255), nullable=False),
            sa.Column("trust_score", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("flags_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("timeouts_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("approved_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "author_channel_id", name="uq_viewer_trust_creator_author"),
        )
        safe_idx(op.f("ix_viewer_trust_profiles_creator_id"), "viewer_trust_profiles", ["creator_id"])
        safe_idx(op.f("ix_viewer_trust_profiles_author_channel_id"), "viewer_trust_profiles", ["author_channel_id"])
        existing_tables.add("viewer_trust_profiles")

    # -------------------------------------------------------------------------
    # 9. ai_usage_records
    # -------------------------------------------------------------------------
    if "ai_usage_records" not in existing_tables:
        op.create_table(
            "ai_usage_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("stream_session_id", sa.String(length=36), nullable=True),
            sa.Column("feature", sa.String(length=32), nullable=False),
            sa.Column("model", sa.String(length=64), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx(op.f("ix_ai_usage_records_creator_id"), "ai_usage_records", ["creator_id"])
        safe_idx(op.f("ix_ai_usage_records_stream_session_id"), "ai_usage_records", ["stream_session_id"])
        safe_idx(op.f("ix_ai_usage_records_created_at"), "ai_usage_records", ["created_at"])
        safe_idx("ix_ai_usage_creator_created", "ai_usage_records", ["creator_id", "created_at"])
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
            sa.Column("persona_name", sa.String(length=64), nullable=False, server_default="Goddess"),
            sa.Column("system_prompt_override", sa.Text(), nullable=True),
            sa.Column("primary_model", sa.String(length=64), nullable=False, server_default="anthropic/claude-3.5-sonnet"),
            sa.Column("fallback_model", sa.String(length=64), nullable=False, server_default="mistralai/mistral-large-2411"),
            sa.Column("strictness_level", sa.String(length=16), nullable=False, server_default="standard"),
            sa.Column("auto_moderation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("hitl_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("ai_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("greeting_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("farewell_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("quiet_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", name="uq_creator_ai_settings_creator_id"),
        )
        safe_idx("ix_creator_ai_settings_creator_id", "creator_ai_settings", ["creator_id"], unique=True)
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
            sa.Column("min_role", sa.String(length=32), nullable=False, server_default="EVERYONE"),
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
        safe_idx("ix_command_aliases_target_id", "command_aliases", ["target_command_id"])
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
            sa.Column("viewer_name", sa.String(length=255), nullable=False),
            sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("command_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("watch_time_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "viewer_channel_id", name="uq_viewer_engagements_creator_viewer"),
        )
        safe_idx("ix_viewer_engagements_creator_id", "viewer_engagements", ["creator_id"])
        safe_idx("ix_viewer_engagements_viewer_channel_id", "viewer_engagements", ["viewer_channel_id"])
        safe_idx("ix_viewer_engagements_xp", "viewer_engagements", ["xp"])
        safe_idx("ix_viewer_engagements_creator_xp", "viewer_engagements", ["creator_id", "xp"])
        existing_tables.add("viewer_engagements")

    # -------------------------------------------------------------------------
    # 13. economy_accounts, economy_transactions, economy_ledger_entries
    # -------------------------------------------------------------------------
    if "economy_accounts" not in existing_tables:
        op.create_table(
            "economy_accounts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("account_holder_type", sa.String(length=32), nullable=False),
            sa.Column("account_holder_id", sa.String(length=128), nullable=False),
            sa.Column("account_type", sa.String(length=32), nullable=False),
            sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "account_holder_type", "account_holder_id", "account_type", name="uq_economy_accounts_holder_type"),
        )
        safe_idx("ix_economy_accounts_creator_id", "economy_accounts", ["creator_id"])
        safe_idx("ix_economy_accounts_holder_id", "economy_accounts", ["account_holder_id"])
        existing_tables.add("economy_accounts")

    if "economy_transactions" not in existing_tables:
        op.create_table(
            "economy_transactions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("transaction_type", sa.String(length=32), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("reference", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "idempotency_key", name="uq_economy_transactions_creator_idempotency"),
        )
        safe_idx("ix_economy_transactions_creator_id", "economy_transactions", ["creator_id"])
        safe_idx("ix_economy_transactions_idempotency", "economy_transactions", ["idempotency_key"])
        existing_tables.add("economy_transactions")

    if "economy_ledger_entries" not in existing_tables:
        op.create_table(
            "economy_ledger_entries",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("transaction_id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=36), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["account_id"], ["economy_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["transaction_id"], ["economy_transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_economy_ledger_entries_transaction_id", "economy_ledger_entries", ["transaction_id"])
        safe_idx("ix_economy_ledger_entries_account_id", "economy_ledger_entries", ["account_id"])
        existing_tables.add("economy_ledger_entries")

    # -------------------------------------------------------------------------
    # 14. store_items & viewer_inventories
    # -------------------------------------------------------------------------
    if "store_items" not in existing_tables:
        op.create_table(
            "store_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("price", sa.Integer(), nullable=False),
            sa.Column("item_type", sa.String(length=32), nullable=False),
            sa.Column("max_per_user", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("stock_remaining", sa.Integer(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_store_items_creator_id", "store_items", ["creator_id"])
        existing_tables.add("store_items")

    if "viewer_inventories" not in existing_tables:
        op.create_table(
            "viewer_inventories",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("viewer_channel_id", sa.String(length=128), nullable=False),
            sa.Column("item_id", sa.String(length=36), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["item_id"], ["store_items.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
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
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("pot_amount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("winner_id", sa.String(length=128), nullable=True),
            sa.Column("game_state", json_type, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        safe_idx("ix_mini_game_sessions_creator_id", "mini_game_sessions", ["creator_id"])
        safe_idx("ix_mini_game_sessions_stream_session_id", "mini_game_sessions", ["stream_session_id"])
        existing_tables.add("mini_game_sessions")


def downgrade() -> None:
    pass
