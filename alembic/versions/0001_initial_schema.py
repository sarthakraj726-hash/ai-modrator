"""Initial schema migration: creators, stream_sessions, audit_events, system_events

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Creators table
    op.create_table(
        "creators",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("youtube_channel_id", sa.String(length=64), nullable=False),
        sa.Column("channel_name", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creators")),
    )
    op.create_index(op.f("ix_creators_youtube_channel_id"), "creators", ["youtube_channel_id"], unique=True)

    # 2. Stream Sessions table
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], name=op.f("fk_stream_sessions_creator_id_creators"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_sessions")),
    )
    op.create_index(op.f("ix_stream_sessions_creator_id"), "stream_sessions", ["creator_id"], unique=False)
    op.create_index(op.f("ix_stream_sessions_youtube_video_id"), "stream_sessions", ["youtube_video_id"], unique=False)
    op.create_index(op.f("ix_stream_sessions_status"), "stream_sessions", ["status"], unique=False)
    op.create_index("ix_stream_sessions_creator_status", "stream_sessions", ["creator_id", "status"], unique=False)
    op.create_index("ix_stream_sessions_video_status", "stream_sessions", ["youtube_video_id", "status"], unique=False)

    # 3. Audit Events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=True),
        sa.Column("stream_session_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="SYSTEM"),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], name=op.f("fk_audit_events_creator_id_creators"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], name=op.f("fk_audit_events_stream_session_id_stream_sessions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_events_creator_id"), "audit_events", ["creator_id"], unique=False)
    op.create_index(op.f("ix_audit_events_stream_session_id"), "audit_events", ["stream_session_id"], unique=False)
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"], unique=False)
    op.create_index("ix_audit_events_type_created", "audit_events", ["event_type", "created_at"], unique=False)
    op.create_index("ix_audit_events_creator_type", "audit_events", ["creator_id", "event_type"], unique=False)

    # 4. System Events table
    op.create_table(
        "system_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="INFO"),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False, server_default="ai-modrator"),
        sa.Column("stream_session_id", sa.String(length=36), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_events")),
    )
    op.create_index(op.f("ix_system_events_severity"), "system_events", ["severity"], unique=False)
    op.create_index(op.f("ix_system_events_event_type"), "system_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_system_events_service"), "system_events", ["service"], unique=False)
    op.create_index(op.f("ix_system_events_stream_session_id"), "system_events", ["stream_session_id"], unique=False)
    op.create_index(op.f("ix_system_events_created_at"), "system_events", ["created_at"], unique=False)
    op.create_index("ix_system_events_sev_created", "system_events", ["severity", "created_at"], unique=False)
    op.create_index("ix_system_events_type_created", "system_events", ["event_type", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("audit_events")
    op.drop_table("stream_sessions")
    op.drop_table("creators")
