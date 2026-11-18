"""e-mail verification (v3.17): users.email_verified_at + email_verifications

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-11-18 21:00:00.000000

Additive. Every EXISTING user is marked verified (they registered before this feature), so nobody is locked out.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = 'b9c0d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP"))
    op.create_table('email_verifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'))
    op.create_index(op.f('ix_email_verifications_user_id'), 'email_verifications', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_email_verifications_user_id'), table_name='email_verifications')
    op.drop_table('email_verifications')
    op.drop_column('users', 'email_verified_at')
