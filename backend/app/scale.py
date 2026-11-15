"""Multi-instance safety for the DB job queue (free). Works on SQLite (single instance) and Postgres (N instances).
 - claim(): on Postgres uses SELECT ... FOR UPDATE SKIP LOCKED so two workers never take the same job.
 - recover_stale(): jobs stuck in 'running' (instance died / redeploy) go back to 'pending' after the lease.
 - leader(): Postgres advisory lock so only one instance runs the scheduler/housekeeping at a time."""
import datetime as dt
from sqlalchemy import select, update, func
from .models2 import AgentJob, AgentEvent
LEASE_MINUTES = 10
def _now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
def is_pg(db) -> bool: return db.bind.dialect.name == "postgresql"

def claim(db):
    q = select(AgentJob).where(AgentJob.status == "pending", AgentJob.run_after <= _now()).order_by(AgentJob.run_after).limit(1)
    if is_pg(db): q = q.with_for_update(skip_locked=True)
    j = db.scalar(q)
    if not j: db.rollback(); return None
    n = db.execute(update(AgentJob).where(AgentJob.id == j.id, AgentJob.status == "pending").values(status="running", attempts=j.attempts + 1)).rowcount
    db.commit()
    if n != 1: return None
    db.refresh(j); return j

def recover_stale(db, lease_minutes: int = LEASE_MINUTES) -> int:
    """Re-queue running jobs whose last 'started' event is older than the lease. attempts already counted, so a
    job that keeps killing its worker still reaches 'dead' via max_attempts."""
    cutoff = _now() - dt.timedelta(minutes=lease_minutes); n = 0
    for j in db.scalars(select(AgentJob).where(AgentJob.status == "running")):
        last = db.scalar(select(func.max(AgentEvent.created_at)).where(AgentEvent.job_id == j.id, AgentEvent.event == "started"))
        if last is None or last.replace(tzinfo=None) < cutoff:
            if j.attempts >= j.max_attempts: j.status, j.finished_at, j.dedupe_key, j.last_error = "dead", _now(), None, "lease expired"
            else: j.status, j.last_error = "pending", "lease expired; re-queued"
            n += 1
    db.commit(); return n

def leader(db, key: int = 7301) -> bool:
    """Session-level advisory lock; non-Postgres is always the leader. Keep the session open while leading."""
    if not is_pg(db): return True
    from sqlalchemy import text
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar())
