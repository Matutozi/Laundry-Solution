"""replace orderstatus pipeline

Revision ID: c567ef5dd1c8
Revises: 044f3326d5be
Create Date: 2026-06-26 20:49:07.217600

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c567ef5dd1c8'
down_revision: Union[str, Sequence[str], None] = '044f3326d5be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "('received','washing','drying','ready','collected','cancelled')"
_NEW = "('received','processing','ready','picked_up','delivered','cancelled')"


def upgrade() -> None:
    # Step 1: cast all enum columns to text so we can freely rename values
    for col in [("orders", "status"), ("status_events", "from_status"), ("status_events", "to_status")]:
        op.execute(f"ALTER TABLE {col[0]} ALTER COLUMN {col[1]} TYPE text USING {col[1]}::text")

    # Step 2: remap old values to new ones
    op.execute("UPDATE orders       SET status      ='processing' WHERE status       IN ('washing','drying')")
    op.execute("UPDATE orders       SET status      ='picked_up'  WHERE status       ='collected'")
    op.execute("UPDATE status_events SET from_status='processing' WHERE from_status  IN ('washing','drying')")
    op.execute("UPDATE status_events SET to_status  ='processing' WHERE to_status    IN ('washing','drying')")
    op.execute("UPDATE status_events SET from_status='picked_up'  WHERE from_status  ='collected'")
    op.execute("UPDATE status_events SET to_status  ='picked_up'  WHERE to_status    ='collected'")

    # Step 3: drop old enum, create new one, convert columns back
    op.execute("DROP TYPE orderstatus")
    op.execute(f"CREATE TYPE orderstatus AS ENUM {_NEW}")
    for col in [("orders", "status"), ("status_events", "from_status"), ("status_events", "to_status")]:
        op.execute(f"ALTER TABLE {col[0]} ALTER COLUMN {col[1]} TYPE orderstatus USING {col[1]}::orderstatus")


def downgrade() -> None:
    for col in [("orders", "status"), ("status_events", "from_status"), ("status_events", "to_status")]:
        op.execute(f"ALTER TABLE {col[0]} ALTER COLUMN {col[1]} TYPE text USING {col[1]}::text")
    op.execute("UPDATE orders SET status='washing'   WHERE status='processing'")
    op.execute("UPDATE orders SET status='collected' WHERE status IN ('picked_up','delivered')")
    op.execute("DROP TYPE orderstatus")
    op.execute(f"CREATE TYPE orderstatus AS ENUM {_OLD}")
    for col in [("orders", "status"), ("status_events", "from_status"), ("status_events", "to_status")]:
        op.execute(f"ALTER TABLE {col[0]} ALTER COLUMN {col[1]} TYPE orderstatus USING {col[1]}::orderstatus")
