"""Phase 3 schema migration: moderation_reviews, moderation_feedback, viewer_trust_profiles, ai_usage_records, creator_ai_settings

Revision ID: 0003_phase3_ai_moderation_persona
Revises: 0002_phase2_youtube_websub
Create Date: 2026-09-03 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_phase3_ai_moderation_persona"
down_revision: Union[str, None] = "0002_phase2_youtube_websub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Moderation Reviews table
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
            sa.Column("recommended_action", sa.String(length=32), nullable=False),
            sa.Column("final_action", sa.String(length=32), nullable=True),
            sa.Column("reason_code", sa.String(length=64), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("language", sa.String(length=32), nullable=False, server_default="en"),
            sa.Column("context_summary", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_moderation_reviews_creator_id"), "moderation_reviews", ["creator_id"], unique=False)
        op.create_index(op.f("ix_moderation_reviews_stream_session_id"), "moderation_reviews", ["stream_session_id"], unique=False)
        op.create_index(op.f("ix_moderation_reviews_message_id"), "moderation_reviews", ["message_id"], unique=False)
        op.create_index(op.f("ix_moderation_reviews_author_channel_id"), "moderation_reviews", ["author_channel_id"], unique=False)
        op.create_index(op.f("ix_moderation_reviews_status"), "moderation_reviews", ["status"], unique=False)
        op.create_index(op.f("ix_moderation_reviews_expires_at"), "moderation_reviews", ["expires_at"], unique=False)
        op.create_index("ix_mod_reviews_creator_status", "moderation_reviews", ["creator_id", "status"], unique=False)
        op.create_index("ix_mod_reviews_session_created", "moderation_reviews", ["stream_session_id", "created_at"], unique=False)

    # 2. Moderation Feedback table
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
        op.create_index(op.f("ix_moderation_feedback_review_id"), "moderation_feedback", ["review_id"], unique=False)
        op.create_index(op.f("ix_moderation_feedback_creator_id"), "moderation_feedback", ["creator_id"], unique=False)
        op.create_index(op.f("ix_moderation_feedback_moderator_id"), "moderation_feedback", ["moderator_id"], unique=False)
        op.create_index("ix_mod_feedback_creator_decision", "moderation_feedback", ["creator_id", "decision"], unique=False)

    # 3. Viewer Trust Profiles table
    if "viewer_trust_profiles" not in existing_tables:
        op.create_table(
            "viewer_trust_profiles",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("viewer_channel_id", sa.String(length=128), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("trust_score", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("messages_seen", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("positive_interactions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("timeout_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hide_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_greeting_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("creator_id", "viewer_channel_id", name="uq_viewer_trust_creator_channel"),
        )
        op.create_index(op.f("ix_viewer_trust_profiles_creator_id"), "viewer_trust_profiles", ["creator_id"], unique=False)
        op.create_index(op.f("ix_viewer_trust_profiles_viewer_channel_id"), "viewer_trust_profiles", ["viewer_channel_id"], unique=False)
        op.create_index("ix_viewer_trust_score", "viewer_trust_profiles", ["creator_id", "trust_score"], unique=False)

    # 4. AI Usage Records table
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
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_ai_usage_records_creator_id"), "ai_usage_records", ["creator_id"], unique=False)
        op.create_index(op.f("ix_ai_usage_records_stream_session_id"), "ai_usage_records", ["stream_session_id"], unique=False)
        op.create_index(op.f("ix_ai_usage_records_model"), "ai_usage_records", ["model"], unique=False)
        op.create_index(op.f("ix_ai_usage_records_task_type"), "ai_usage_records", ["task_type"], unique=False)
        op.create_index("ix_ai_usage_creator_task", "ai_usage_records", ["creator_id", "task_type"], unique=False)
        op.create_index("ix_ai_usage_created_at", "ai_usage_records", ["created_at"], unique=False)

    # 5. Creator AI Settings table
    if "creator_ai_settings" not in existing_tables:
        op.create_table(
            "creator_ai_settings",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("creator_id", sa.String(length=36), nullable=False),
            sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("persona_type", sa.String(length=32), nullable=False, server_default="CO_HOST"),
            sa.Column("persona_sliders", sa.JSON(), nullable=False),
            sa.Column("custom_persona_prompt", sa.Text(), nullable=True),
            sa.Column("moderation_strictness", sa.String(length=32), nullable=False, server_default="BALANCED"),
            sa.Column("moderation_mode", sa.String(length=32), nullable=False, server_default="ACTIVE"),
            sa.Column("auto_moderation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("hitl_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("ai_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("greeting_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("farewell_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("quiet_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("max_ai_messages_per_minute", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("ai_daily_budget", sa.Integer(), nullable=False, server_default="1000"),
            sa.Column("custom_rules", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_creator_ai_settings_creator_id"), "creator_ai_settings", ["creator_id"], unique=True)


def downgrade() -> None:
    op.drop_table("creator_ai_settings")
    op.drop_table("ai_usage_records")
    op.drop_table("viewer_trust_profiles")
    op.drop_table("moderation_feedback")
    op.drop_table("moderation_reviews")
