"""merge heads: payments_receipts + perf_indexes

Revision ID: b9c0d1e2f3a4
Revises: a8c9d0e1f2b3, a9b8c7d6e5f4
"""
from typing import Sequence, Union

revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = ('a8c9d0e1f2b3', 'a9b8c7d6e5f4')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
