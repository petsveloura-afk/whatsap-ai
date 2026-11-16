"""agent_memory and agent_messages (v3.3 agent)

Revision ID: f4b5c6d7e8a9
Revises: d3a4b5c6e7f8
Create Date: 2026-11-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f4b5c6d7e8a9'
down_revision: Union[str, None] = 'd3a4b5c6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_memory',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('text', sa.String(length=500), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=True),
    sa.Column('uses', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_memory_user_id'), 'agent_memory', ['user_id'], unique=False)
    op.create_table('agent_messages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('actions', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_messages_user_id'), 'agent_messages', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_messages_user_id'), table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index(op.f('ix_agent_memory_user_id'), table_name='agent_memory')
    op.drop_table('agent_memory')
