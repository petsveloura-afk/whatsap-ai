"""performance indexes (v3.16, additive: indexes only, no table or column is touched)

Revision ID: a9b8c7d6e5f4
Revises: f4b5c6d7e8a9
Create Date: 2026-11-17 09:00:00.000000

Speeds up the queries the dashboard, the agent, the profile page and the exports run most:
listings by (user, status, newest first), listings by (user, score), agent memory / history by (user, newest first).
`if_not_exists` / `if_exists` make the migration safe to re-run and safe on databases that already have an index of that name.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'f4b5c6d7e8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_listings_user_status_created", "listings", ["user_id", "status", "created_at"]),
    ("ix_listings_user_score", "listings", ["user_id", "score"]),
    ("ix_agent_memory_user_created", "agent_memory", ["user_id", "created_at"]),
    ("ix_agent_messages_user_created", "agent_messages", ["user_id", "created_at"]),
]


def upgrade() -> None:
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols, unique=False, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
