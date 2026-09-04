"""Phase 2 schema migration: websub_subscriptions, discovery_events, checkpoints

Revision ID: 0002_phase2_youtube_websub
Revises: 0001_initial_schema
Create Date: 2026-09-02 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_phase2_youtube_websub"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. WebSub Subscriptions table
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
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], name=op.f("fk_websub_creator_id_creators"), ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_websub_subscriptions")),
        )
        op.create_index(op.f("ix_youtube_websub_subscriptions_creator_id"), "youtube_websub_subscriptions", ["creator_id"], unique=False)
        op.create_index(op.f("ix_youtube_websub_subscriptions_channel_id"), "youtube_websub_subscriptions", ["channel_id"], unique=False)
        op.create_index(op.f("ix_youtube_websub_subscriptions_topic_url"), "youtube_websub_subscriptions", ["topic_url"], unique=False)
        op.create_index(op.f("ix_youtube_websub_subscriptions_status"), "youtube_websub_subscriptions", ["status"], unique=False)
        op.create_index("ix_websub_channel_status", "youtube_websub_subscriptions", ["channel_id", "status"], unique=False)
        op.create_index("ix_websub_lease_expiry", "youtube_websub_subscriptions", ["lease_expires_at"], unique=False)

    # 2. YouTube Discovery Events table
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
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_discovery_events")),
        )
        op.create_index(op.f("ix_youtube_discovery_events_creator_id"), "youtube_discovery_events", ["creator_id"], unique=False)
        op.create_index(op.f("ix_youtube_discovery_events_channel_id"), "youtube_discovery_events", ["channel_id"], unique=False)
        op.create_index(op.f("ix_youtube_discovery_events_video_id"), "youtube_discovery_events", ["video_id"], unique=False)
        op.create_index(op.f("ix_youtube_discovery_events_event_type"), "youtube_discovery_events", ["event_type"], unique=False)
        op.create_index(op.f("ix_youtube_discovery_events_dedupe_hash"), "youtube_discovery_events", ["dedupe_hash"], unique=False)
        op.create_index(op.f("ix_youtube_discovery_events_processed"), "youtube_discovery_events", ["processed"], unique=False)
        op.create_index(op.f("ix_youtube_discovery_events_received_at"), "youtube_discovery_events", ["received_at"], unique=False)
        op.create_index("ix_discovery_dedupe_processed", "youtube_discovery_events", ["dedupe_hash", "processed"], unique=False)
        op.create_index("ix_discovery_video_processed", "youtube_discovery_events", ["video_id", "processed"], unique=False)

    # 3. YouTube Checkpoints table
    if "youtube_checkpoints" not in existing_tables:
        op.create_table(
            "youtube_checkpoints",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("stream_session_id", sa.String(length=36), nullable=False),
            sa.Column("last_next_page_token", sa.String(length=255), nullable=True),
            sa.Column("last_message_id", sa.String(length=128), nullable=True),
            sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_messages_ingested", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], name=op.f("fk_checkpoints_session_id_stream_sessions"), ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_youtube_checkpoints")),
        )
        op.create_index(op.f("ix_youtube_checkpoints_stream_session_id"), "youtube_checkpoints", ["stream_session_id"], unique=True)


def downgrade() -> None:
    op.drop_table("youtube_checkpoints")
    op.drop_table("youtube_discovery_events")
    op.drop_table("youtube_websub_subscriptions")
