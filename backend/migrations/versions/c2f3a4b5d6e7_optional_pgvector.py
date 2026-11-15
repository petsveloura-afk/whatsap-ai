"""optional_pgvector: no-op unless Postgres AND env USE_PGVECTOR=1

Revision ID: c2f3a4b5d6e7
Revises: b1e2f3a4c5d6
"""
import os
from typing import Sequence, Union
from alembic import op

revision: str = 'c2f3a4b5d6e7'
down_revision: Union[str, None] = 'b1e2f3a4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _on() -> bool: return op.get_bind().dialect.name == "postgresql" and os.environ.get("USE_PGVECTOR") == "1"

def upgrade() -> None:
    if not _on(): return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE ai_embeddings ADD COLUMN IF NOT EXISTS vec vector(256)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_embeddings_vec ON ai_embeddings USING hnsw (vec vector_cosine_ops)")

def downgrade() -> None:
    if not _on(): return
    op.execute("DROP INDEX IF EXISTS ix_ai_embeddings_vec")
    op.execute("ALTER TABLE ai_embeddings DROP COLUMN IF EXISTS vec")
