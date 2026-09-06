"""Historical migration restoration: 002_add_join_message_sent.

Revision ID: 002_add_join_message_sent
Revises: None
Create Date: 2026-09-02 00:00:00.000000

This migration restores the canonical ancestry for the historical revision
'002_add_join_message_sent' present in the production PostgreSQL database.
It is designed to be fully idempotent:
- On production databases where this revision already ran, Alembic recognizes it
  and safely advances to the merge reconciliation migration.
- On clean/fresh databases, this migration executes safely without failing even
  if 'stream_sessions' has not yet been created by the parallel branch.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_join_message_sent"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # If stream_sessions exists, ensure join_message_sent column is present idempotently.
    if "stream_sessions" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("stream_sessions")}
        if "join_message_sent" not in cols:
            op.add_column(
                "stream_sessions",
                sa.Column(
                    "join_message_sent",
                    sa.Boolean(),
                    nullable=True,
                    server_default=sa.text("false"),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "stream_sessions" in existing_tables:
        cols = {c["name"] for c in insp.get_columns("stream_sessions")}
        if "join_message_sent" in cols:
            op.drop_column("stream_sessions", "join_message_sent")
