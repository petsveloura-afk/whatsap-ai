"""payments, receipts and prepaid subscription periods (v3.15)

Revision ID: a8c9d0e1f2b3
Revises: f4b5c6d7e8a9
Create Date: 2026-11-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a8c9d0e1f2b3'
down_revision: Union[str, None] = 'f4b5c6d7e8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive only: three nullable columns on subscriptions + one new table. Existing rows keep working unchanged.
    op.add_column('subscriptions', sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('billing_period', sa.String(length=10), nullable=True))
    op.add_column('subscriptions', sa.Column('renewal_reminded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('payments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('customer_id', sa.String(length=36), nullable=False),
    sa.Column('customer_email', sa.String(length=255), nullable=False),
    sa.Column('plan', sa.String(length=20), nullable=False),
    sa.Column('period', sa.String(length=10), nullable=False),
    sa.Column('amount', sa.String(length=16), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('method', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('paypal_order_id', sa.String(length=64), nullable=True),
    sa.Column('paypal_capture_id', sa.String(length=64), nullable=True),
    sa.Column('payer_email', sa.String(length=255), nullable=True),
    sa.Column('card_brand', sa.String(length=24), nullable=True),
    sa.Column('card_last4', sa.String(length=4), nullable=True),
    sa.Column('receipt_no', sa.String(length=32), nullable=True),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failure_reason', sa.String(length=200), nullable=True),
    sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('paypal_order_id'),
    sa.UniqueConstraint('paypal_capture_id'),
    sa.UniqueConstraint('receipt_no')
    )
    op.create_index(op.f('ix_payments_customer_id'), 'payments', ['customer_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_customer_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_column('subscriptions', 'renewal_reminded_at')
    op.drop_column('subscriptions', 'billing_period')
    op.drop_column('subscriptions', 'current_period_end')
