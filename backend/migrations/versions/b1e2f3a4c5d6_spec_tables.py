"""spec_tables: remaining tables from the specification

Revision ID: b1e2f3a4c5d6
Revises: a7c1d2e3f4b5
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1e2f3a4c5d6'
down_revision: Union[str, None] = 'a7c1d2e3f4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID = lambda: sa.Column('id', sa.String(36), primary_key=True)
S = lambda n, l=255, null=False: sa.Column(n, sa.String(l), nullable=null)
I = lambda n, null=False: sa.Column(n, sa.Integer(), nullable=null)
F = lambda n, null=True: sa.Column(n, sa.Float(), nullable=null)
B = lambda n: sa.Column(n, sa.Boolean(), nullable=False, server_default=sa.false())
J = lambda n, null=False: sa.Column(n, sa.JSON(), nullable=null)
T = lambda n="created_at", null=False: sa.Column(n, sa.DateTime(timezone=True), nullable=null)
FK = lambda n, t, null=False: sa.Column(n, sa.String(36), sa.ForeignKey(t + '.id'), nullable=null)
IX = lambda t, c: op.create_index(f'ix_{t}_{c}', t, [c])


def upgrade() -> None:
    op.create_table('roles', ID(), S('name', 30), S('description', 200, True), sa.UniqueConstraint('name'))
    op.create_table('permissions', ID(), S('role', 30), S('permission', 60), sa.UniqueConstraint('role', 'permission'))
    IX('permissions', 'role')
    op.create_table('user_profiles', ID(), FK('user_id', 'users'), S('display_name', 80, True), S('locale', 10), S('timezone', 50), sa.UniqueConstraint('user_id'))
    op.create_table('data_sources', ID(), FK('user_id', 'users'), FK('search_id', 'search_configs'), S('kind', 20), S('url', 1000), I('interval_minutes'),
                    sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()), S('status', 20), S('last_error', 300, True), T('last_polled_at', True), T())
    IX('data_sources', 'user_id'); IX('data_sources', 'search_id')
    op.create_table('search_sources', ID(), FK('search_id', 'search_configs'), FK('source_id', 'data_sources'), sa.UniqueConstraint('search_id', 'source_id'))
    IX('search_sources', 'search_id'); IX('search_sources', 'source_id')
    op.create_table('ingestion_events', ID(), FK('user_id', 'users'), S('source_id', 36, True), S('channel', 20), S('status', 20), S('detail', 300, True), F('latency_ms'), T())
    IX('ingestion_events', 'user_id'); IX('ingestion_events', 'source_id')
    op.create_table('listing_images', ID(), FK('listing_id', 'listings'), S('url', 1000)); IX('listing_images', 'listing_id')
    op.create_table('listing_deduplication', ID(), FK('user_id', 'users'), S('search_id', 36), S('kind', 20), F('similarity'), T()); IX('listing_deduplication', 'user_id')
    op.create_table('listing_scores', ID(), FK('listing_id', 'listings'), I('score'), J('detail'), T()); IX('listing_scores', 'listing_id')
    op.create_table('user_listing_actions', ID(), FK('user_id', 'users'), FK('listing_id', 'listings'), S('action', 20), T())
    IX('user_listing_actions', 'user_id'); IX('user_listing_actions', 'listing_id')
    op.create_table('ai_embeddings', ID(), FK('user_id', 'users'), S('memory_id', 36, True), J('embedding'), T()); IX('ai_embeddings', 'user_id'); IX('ai_embeddings', 'memory_id')
    op.create_table('agent_jobs', ID(), S('user_id', 36, True), S('kind', 30), J('payload'), S('status', 12), I('attempts'), I('max_attempts'), T('run_after'),
                    S('dedupe_key', 120, True), S('last_error', 300, True), T(), T('finished_at', True), sa.UniqueConstraint('dedupe_key'))
    IX('agent_jobs', 'user_id'); IX('agent_jobs', 'status')
    op.create_table('agent_events', ID(), S('agent', 30), S('event', 30), S('job_id', 36, True), F('duration_ms'), S('detail', 300, True), T()); IX('agent_events', 'agent')
    op.create_table('notification_preferences', ID(), FK('user_id', 'users'), sa.Column('in_app', sa.Boolean(), nullable=False, server_default=sa.true()), B('email'), I('min_score'), sa.UniqueConstraint('user_id'))
    op.create_table('notifications', ID(), FK('user_id', 'users'), S('title', 200), S('body', 500, True), S('listing_id', 36, True), B('read'), T()); IX('notifications', 'user_id')
    op.create_table('integrations', ID(), FK('user_id', 'users'), S('provider', 30), S('status', 20), T()); IX('integrations', 'user_id')
    op.create_table('integration_sessions', ID(), FK('integration_id', 'integrations'), S('state', 20), T()); IX('integration_sessions', 'integration_id')
    op.create_table('whatsapp_connections', ID(), FK('user_id', 'users'), S('number', 20), T('consent_at', True), sa.UniqueConstraint('user_id'))
    op.create_table('system_settings', sa.Column('key', sa.String(60), primary_key=True), J('value'), T('updated_at'))
    op.create_table('admin_actions', ID(), S('admin_id', 36), S('action', 60), S('target', 120, True), J('detail', True), T()); IX('admin_actions', 'admin_id')


def downgrade() -> None:
    for t in ('admin_actions', 'system_settings', 'whatsapp_connections', 'integration_sessions', 'integrations', 'notifications', 'notification_preferences',
              'agent_events', 'agent_jobs', 'ai_embeddings', 'user_listing_actions', 'listing_scores', 'listing_deduplication', 'listing_images',
              'ingestion_events', 'search_sources', 'data_sources', 'user_profiles', 'permissions', 'roles'):
        op.drop_table(t)
