"""Phase 4 schema migration: custom_commands, command_aliases, viewer_engagements, economy_accounts, economy_transactions, economy_ledger_entries, store_items, viewer_inventories, mini_game_sessions.

Revision ID: 0004_phase4_engagement_economy
Revises: 0003_phase3_ai_moderation_persona
Create Date: 2026-09-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_phase4_engagement_economy"
down_revision: Union[str, None] = "0003_phase3_ai_moderation_persona"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Custom Commands
    op.create_table(
        "custom_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("min_role", sa.String(length=32), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "name", name="uq_custom_commands_creator_name"),
    )
    op.create_index("ix_custom_commands_creator_id", "custom_commands", ["creator_id"])
    op.create_index("ix_custom_commands_creator_name", "custom_commands", ["creator_id", "name"])

    # 2. Command Aliases
    op.create_table(
        "command_aliases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("alias", sa.String(length=64), nullable=False),
        sa.Column("target_command_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_command_id"], ["custom_commands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "alias", name="uq_command_aliases_creator_alias"),
    )
    op.create_index("ix_command_aliases_creator_id", "command_aliases", ["creator_id"])
    op.create_index("ix_command_aliases_target_id", "command_aliases", ["target_command_id"])
    op.create_index("ix_command_aliases_creator_alias", "command_aliases", ["creator_id", "alias"])

    # 3. Viewer Engagements
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
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "viewer_channel_id", name="uq_viewer_engagement_creator_viewer"),
    )
    op.create_index("ix_viewer_engagements_creator_id", "viewer_engagements", ["creator_id"])
    op.create_index("ix_viewer_engagements_viewer_channel_id", "viewer_engagements", ["viewer_channel_id"])
    op.create_index("ix_viewer_engagement_xp", "viewer_engagements", ["creator_id", "total_xp"])
    op.create_index("ix_viewer_engagement_level", "viewer_engagements", ["creator_id", "level"])

    # 4. Economy Accounts
    op.create_table(
        "economy_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("viewer_channel_id", sa.String(length=128), nullable=True),
        sa.Column("account_type", sa.String(length=32), nullable=False, server_default="VIEWER"),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "viewer_channel_id", "account_type", name="uq_economy_account_creator_viewer_type"),
    )
    op.create_index("ix_economy_accounts_creator_id", "economy_accounts", ["creator_id"])
    op.create_index("ix_economy_accounts_viewer_id", "economy_accounts", ["viewer_channel_id"])
    op.create_index("ix_economy_account_creator_balance", "economy_accounts", ["creator_id", "balance"])

    # 5. Economy Transactions
    op.create_table(
        "economy_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "idempotency_key", name="uq_economy_tx_creator_idempotency"),
    )
    op.create_index("ix_economy_transactions_creator_id", "economy_transactions", ["creator_id"])
    op.create_index("ix_economy_tx_creator_created", "economy_transactions", ["creator_id", "created_at"])

    # 6. Economy Ledger Entries
    op.create_table(
        "economy_ledger_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["economy_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["economy_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_economy_ledger_transaction_id", "economy_ledger_entries", ["transaction_id"])
    op.create_index("ix_economy_ledger_account_id", "economy_ledger_entries", ["account_id"])
    op.create_index("ix_economy_ledger_account_created", "economy_ledger_entries", ["account_id", "created_at"])

    # 7. Store Items
    op.create_table(
        "store_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("max_per_user", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "name", name="uq_store_items_creator_name"),
    )
    op.create_index("ix_store_items_creator_id", "store_items", ["creator_id"])
    op.create_index("ix_store_items_creator_enabled", "store_items", ["creator_id", "enabled"])

    # 8. Viewer Inventories
    op.create_table(
        "viewer_inventories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("viewer_channel_id", sa.String(length=128), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["store_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "viewer_channel_id", "item_id", name="uq_viewer_inventory_creator_viewer_item"),
    )
    op.create_index("ix_viewer_inventories_creator_id", "viewer_inventories", ["creator_id"])
    op.create_index("ix_viewer_inventories_viewer_id", "viewer_inventories", ["viewer_channel_id"])
    op.create_index("ix_viewer_inventories_item_id", "viewer_inventories", ["item_id"])

    # 9. Mini Game Sessions
    op.create_table(
        "mini_game_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creator_id", sa.String(length=36), nullable=False),
        sa.Column("stream_session_id", sa.String(length=36), nullable=False),
        sa.Column("game_type", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("prompt_text", sa.String(length=255), nullable=False),
        sa.Column("solution_data", sa.JSON(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("winner_channel_id", sa.String(length=128), nullable=True),
        sa.Column("winner_display_name", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stream_session_id"], ["stream_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mini_games_creator_id", "mini_game_sessions", ["creator_id"])
    op.create_index("ix_mini_games_session_id", "mini_game_sessions", ["stream_session_id"])
    op.create_index("ix_mini_games_creator_state", "mini_game_sessions", ["creator_id", "state"])
    op.create_index("ix_mini_games_session_state", "mini_game_sessions", ["stream_session_id", "state"])


def downgrade() -> None:
    op.drop_table("mini_game_sessions")
    op.drop_table("viewer_inventories")
    op.drop_table("store_items")
    op.drop_table("economy_ledger_entries")
    op.drop_table("economy_transactions")
    op.drop_table("economy_accounts")
    op.drop_table("viewer_engagements")
    op.drop_table("command_aliases")
    op.drop_table("custom_commands")
