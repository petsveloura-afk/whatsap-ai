"""OPTIONAL pgvector support (Postgres only; Neon/Supabase free tiers include the extension).
Active only when: env USE_PGVECTOR=1 AND flag `pgvector` AND dialect is postgresql AND the optional
Alembic revision c2f3a4b5d6e7 has run. Local 256-dim embeddings are stored in ai_embeddings.vec."""
import json, os, uuid, datetime as dt
from sqlalchemy import text
def enabled(db, flag_on: bool) -> bool:
    return flag_on and os.environ.get("USE_PGVECTOR") == "1" and db.get_bind().dialect.name == "postgresql"
def _lit(v): return "[" + ",".join(f"{x:.6f}" for x in v) + "]"
def store(db, user_id, memory_id, vec):
    db.execute(text("INSERT INTO ai_embeddings (id,user_id,memory_id,embedding,created_at,vec) VALUES (:i,:u,:m,CAST(:e AS json),:t,CAST(:v AS vector))"),
               {"i": str(uuid.uuid4()), "u": user_id, "m": memory_id, "e": json.dumps(vec), "t": dt.datetime.now(dt.timezone.utc), "v": _lit(vec)})
def similar(db, user_id, vec, k=5):
    rows = db.execute(text("SELECT m.id, m.kind, m.text, 1 - (e.vec <=> CAST(:v AS vector)) AS sim FROM ai_embeddings e JOIN ai_memory m ON m.id = e.memory_id "
                           "WHERE e.user_id = :u ORDER BY e.vec <=> CAST(:v AS vector) LIMIT :k"), {"v": _lit(vec), "u": user_id, "k": k}).all()
    return [{"id": r[0], "kind": r[1], "text": r[2][:200], "similarity": round(float(r[3]), 3)} for r in rows]
