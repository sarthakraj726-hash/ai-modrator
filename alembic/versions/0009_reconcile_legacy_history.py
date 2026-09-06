"""Reconcile legacy foreign revision 002_add_join_message_sent with canonical 0008 head.

Revision ID: 0009_reconcile_legacy_history
Revises: 0008_reconcile_missing_core_tables, 002_add_join_message_sent
Create Date: 2026-09-06 15:00:00.000000

This merge migration unifies the canonical migration chain (0001 -> 0008)
with the historical branch '002_add_join_message_sent' into a single head.
It also idempotently verifies schema alignment for operational tables.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_reconcile_legacy_history"
down_revision: Union[str, Sequence[str], None] = (
    "0008_reconcile_missing_core_tables",
    "002_add_join_message_sent",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    is_sqlite = bind.dialect.name == "sqlite"
    is_pg = bind.dialect.name == "postgresql"

    # Helper functions for idempotency
    def safe_idx(name: str, table: str, cols: list[str], unique: bool = False) -> None:
        if table in existing_tables:
            try:
                if is_pg:
                    uniq_clause = "UNIQUE " if unique else ""
                    col_clause = ", ".join(f'"{c}"' for c in cols)
                    bind.execute(
                        sa.text(
                            f'CREATE {uniq_clause}INDEX IF NOT EXISTS "{name}" ON "{table}" ({col_clause});'
                        )
                    )
                else:
                    current_idxs = {i["name"] for i in insp.get_indexes(table)}
                    if name not in current_idxs:
                        op.create_index(name, table, cols, unique=unique)
            except Exception:
                pass

    # 1. Reconcile feature_flags schema if table exists
    if "feature_flags" in existing_tables:
        current_cols = {c["name"] for c in insp.get_columns("feature_flags")}
        if "stream_session_id" not in current_cols:
            if is_sqlite:
                with op.batch_alter_table("feature_flags") as batch_op:
                    batch_op.add_column(
                        sa.Column("stream_session_id", sa.String(length=36), nullable=True)
                    )
            else:
                op.add_column(
                    "feature_flags",
                    sa.Column(
                        "stream_session_id",
                        sa.String(length=36),
                        sa.ForeignKey("stream_sessions.id", ondelete="CASCADE"),
                        nullable=True,
                    ),
                )
        safe_idx("ix_feature_flags_stream_session_id", "feature_flags", ["stream_session_id"])

    # 2. Reconcile incidents stream_session_id index if incidents exists
    if "incidents" in existing_tables:
        safe_idx("ix_incidents_stream_session_id", "incidents", ["stream_session_id"])


def downgrade() -> None:
    pass
