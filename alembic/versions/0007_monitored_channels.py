"""Create monitored_channels table with auto-join configuration.

Revision ID: 0007_monitored_channels
Revises: 0006_reconcile_production_schema
Create Date: 2026-09-05 13:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_create_monitored_channels"
down_revision: Union[str, None] = "0006_reconcile_production_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    def safe_idx(name: str, table: str, cols: list[str], unique: bool = False) -> None:
        current_idxs = {i["name"] for i in insp.get_indexes(table)}
        if name not in current_idxs:
            op.create_index(name, table, cols, unique=unique)

    def safe_add_col(table: str, col: sa.Column) -> None:
        current_cols = {c["name"] for c in insp.get_columns(table)}
        if col.name not in current_cols:
            op.add_column(table, col)

    if "monitored_channels" not in existing_tables:
        op.create_table(
            "monitored_channels",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "creator_id",
                sa.String(length=36),
                sa.ForeignKey("creators.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("youtube_channel_id", sa.String(length=64), nullable=False),
            sa.Column("channel_name", sa.String(length=255), nullable=False),
            sa.Column("channel_handle", sa.String(length=64), nullable=True),
            sa.Column("display_label", sa.String(length=255), nullable=True),
            sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
            sa.Column(
                "enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "auto_join_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "verification_status",
                sa.String(length=32),
                nullable=False,
                server_default="VERIFIED",
            ),
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_live_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_video_id", sa.String(length=64), nullable=True),
            sa.Column("last_connected_stream_session_id", sa.String(length=36), nullable=True),
            sa.Column("last_error_code", sa.String(length=64), nullable=True),
            sa.Column("last_error_message_safe", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "creator_id",
                "youtube_channel_id",
                name="uq_monitored_channels_creator_channel",
            ),
        )

    # Re-inspect to ensure columns and indexes exist
    insp = sa.inspect(bind)
    if "monitored_channels" in insp.get_table_names():
        safe_add_col("monitored_channels", sa.Column("thumbnail_url", sa.String(512), nullable=True))
        safe_add_col("monitored_channels", sa.Column("last_connected_stream_session_id", sa.String(36), nullable=True))
        safe_add_col("monitored_channels", sa.Column("last_connected_session_id", sa.String(36), nullable=True))
        safe_idx("ix_monitored_channels_creator_id", "monitored_channels", ["creator_id"])
        safe_idx(
            "ix_monitored_channels_youtube_channel_id",
            "monitored_channels",
            ["youtube_channel_id"],
        )
        safe_idx(
            "ix_monitored_channels_active",
            "monitored_channels",
            ["enabled", "auto_join_enabled"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "monitored_channels" in existing_tables:
        op.drop_table("monitored_channels")
