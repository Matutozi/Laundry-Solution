"""add order turnaround total_kobo and order_line prices

Revision ID: 044f3326d5be
Revises: 118f4fed3cc1
Create Date: 2026-06-26 20:40:24.577585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '044f3326d5be'
down_revision: Union[str, Sequence[str], None] = '118f4fed3cc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

turnaround_enum = sa.Enum('regular', 'express', 'same_day', name='turnaround')


def upgrade() -> None:
    turnaround_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('order_lines', sa.Column('unit_price_kobo', sa.BigInteger(), nullable=False))
    op.add_column('order_lines', sa.Column('line_total_kobo', sa.BigInteger(), nullable=False))
    op.add_column('orders', sa.Column('turnaround', turnaround_enum, nullable=False))
    op.add_column('orders', sa.Column('total_kobo', sa.BigInteger(), nullable=False))
    op.create_check_constraint('ck_order_total_kobo_non_negative', 'orders', 'total_kobo >= 0')
    op.create_check_constraint('ck_order_line_unit_price_non_negative', 'order_lines', 'unit_price_kobo >= 0')
    op.create_check_constraint('ck_order_line_total_non_negative', 'order_lines', 'line_total_kobo >= 0')


def downgrade() -> None:
    op.drop_constraint('ck_order_line_total_non_negative', 'order_lines')
    op.drop_constraint('ck_order_line_unit_price_non_negative', 'order_lines')
    op.drop_constraint('ck_order_total_kobo_non_negative', 'orders')
    op.drop_column('orders', 'total_kobo')
    op.drop_column('orders', 'turnaround')
    op.drop_column('order_lines', 'line_total_kobo')
    op.drop_column('order_lines', 'unit_price_kobo')
    turnaround_enum.drop(op.get_bind(), checkfirst=True)
