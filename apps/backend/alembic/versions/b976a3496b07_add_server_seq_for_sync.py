"""add_server_seq_for_sync

Revision ID: b976a3496b07
Revises: c567ef5dd1c8
Create Date: 2026-06-26 21:09:39.466149

Adds:
  - PostgreSQL SEQUENCE sync_global_seq — monotonically increasing counter used
    as the server version for WatermelonDB sync.  Never uses device clocks.
  - server_seq BIGINT column on orders, payments, customers.
  - Indexes on those columns for efficient pull queries (WHERE server_seq > ?).
  - Backfills existing rows by assigning each a unique seq value.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b976a3496b07"
down_revision: Union[str, Sequence[str], None] = "c567ef5dd1c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS sync_global_seq START 1 INCREMENT 1")

    for table in ("orders", "payments", "customers"):
        op.add_column(table, sa.Column("server_seq", sa.BigInteger, nullable=True))
        # Backfill existing rows — order doesn't matter, just needs to be unique
        op.execute(
            f"UPDATE {table} SET server_seq = nextval('sync_global_seq')"
        )
        op.create_index(f"ix_{table}_server_seq", table, ["server_seq"])


def downgrade() -> None:
    for table in ("orders", "payments", "customers"):
        op.drop_index(f"ix_{table}_server_seq", table_name=table)
        op.drop_column(table, "server_seq")

    op.execute("DROP SEQUENCE IF EXISTS sync_global_seq")
