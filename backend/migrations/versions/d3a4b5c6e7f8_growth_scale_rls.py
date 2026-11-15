"""growth_scale_rls: api_keys, webhooks, referrals, shared links, user flags, market observations, rate_hits, error_events + Postgres RLS policies

Revision ID: d3a4b5c6e7f8
Revises: c2f3a4b5d6e7
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd3a4b5c6e7f8'
down_revision: Union[str, None] = 'c2f3a4b5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ID = lambda: sa.Column('id', sa.String(36), primary_key=True)
S = lambda n, l=255, null=False: sa.Column(n, sa.String(l), nullable=null)
I = lambda n, d=None: sa.Column(n, sa.Integer(), nullable=False, server_default=None if d is None else str(d))
B = lambda n, d=False: sa.Column(n, sa.Boolean(), nullable=False, server_default=sa.true() if d else sa.false())
T = lambda n="created_at", null=False: sa.Column(n, sa.DateTime(timezone=True), nullable=null)
FK = lambda n='user_id': sa.Column(n, sa.String(36), sa.ForeignKey('users.id'), nullable=False)
RLS = ["search_configs", "listings", "telegram_connections", "refresh_tokens", "password_resets", "subscriptions", "payment_transactions",
       "user_preferences", "ai_memory", "user_profiles", "data_sources", "ingestion_events", "listing_deduplication",
       "user_listing_actions", "notification_preferences", "notifications", "api_keys", "webhook_endpoints",
       "webhook_deliveries", "referrals", "shared_links", "user_flags"]

def upgrade() -> None:
    op.create_table('api_keys', ID(), FK(), S('name', 60), S('prefix', 12), S('key_hash', 64), sa.Column('scopes', sa.JSON(), nullable=False), B('active', True), T('last_used_at', True), T(), sa.UniqueConstraint('key_hash'))
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id']); op.create_index('ix_api_keys_prefix', 'api_keys', ['prefix'])
    op.create_table('webhook_endpoints', ID(), FK(), S('url', 1000), S('secret', 64), I('min_score', 60), B('active', True), T('cursor_at', True), I('fail_count', 0), T())
    op.create_index('ix_webhook_endpoints_user_id', 'webhook_endpoints', ['user_id'])
    op.create_table('webhook_deliveries', ID(), FK(), S('endpoint_id', 36), S('listing_id', 36, True), S('status', 12), sa.Column('http_status', sa.Integer(), nullable=True), S('detail', 300, True), T())
    op.create_index('ix_webhook_deliveries_user_id', 'webhook_deliveries', ['user_id']); op.create_index('ix_webhook_deliveries_endpoint_id', 'webhook_deliveries', ['endpoint_id'])
    op.create_table('referrals', ID(), FK(), S('code', 16, True), S('referred_user_id', 36, True), T(), sa.UniqueConstraint('code'), sa.UniqueConstraint('referred_user_id'))
    op.create_index('ix_referrals_user_id', 'referrals', ['user_id'])
    op.create_table('shared_links', ID(), FK(), S('listing_id', 36), S('token_hash', 64), T('expires_at'), B('revoked'), T(), sa.UniqueConstraint('token_hash'))
    op.create_index('ix_shared_links_user_id', 'shared_links', ['user_id']); op.create_index('ix_shared_links_listing_id', 'shared_links', ['listing_id'])
    op.create_table('user_flags', ID(), FK(), S('name', 40), B('value'), sa.UniqueConstraint('user_id', 'name'))
    op.create_index('ix_user_flags_user_id', 'user_flags', ['user_id'])
    op.create_table('market_observations', ID(), S('category', 40), S('location', 120, True), sa.Column('rooms', sa.Float(), nullable=True), sa.Column('price', sa.Float(), nullable=False), T('observed_at'))
    op.create_index('ix_market_observations_category', 'market_observations', ['category']); op.create_index('ix_market_observations_location', 'market_observations', ['location'])
    op.create_table('rate_hits', ID(), S('key', 200), sa.Column('at', sa.Float(), nullable=False))
    op.create_index('ix_rate_hits_key', 'rate_hits', ['key']); op.create_index('ix_rate_hits_at', 'rate_hits', ['at'])
    op.create_table('error_events', ID(), S('fingerprint', 40), S('kind', 80), S('message', 300), S('route', 200), I('count', 1), sa.Column('sample', sa.Text(), nullable=True), B('resolved'), T('first_seen'), T('last_seen'), sa.UniqueConstraint('fingerprint'))
    if op.get_bind().dialect.name == "postgresql":
        from app.rls import policy_sql
        for t in RLS:
            for stmt in policy_sql(t): op.execute(stmt)   # ENABLE (not FORCE): no effect for the owner role until you opt in, see docs/SECURITY.md

def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in RLS:
            op.execute(f"DROP POLICY IF EXISTS user_isolation ON {t}"); op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    for t in ("error_events", "rate_hits", "market_observations", "user_flags", "shared_links", "referrals", "webhook_deliveries", "webhook_endpoints", "api_keys"): op.drop_table(t)
