"""DB-backed job queue (free, durable). Optional Redis only wakes workers (REDIS_URL); jobs stay in the DB."""
import os, datetime as dt, logging
from sqlalchemy import select, update
from .models2 import AgentJob, AgentEvent
log = logging.getLogger("sniper")

def _now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
_redis = None
def _r():
    global _redis
    if _redis is None and os.environ.get("REDIS_URL"):
        try:
            import redis; _redis = redis.Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3)
        except Exception as e: log.warning("redis unavailable: %s", type(e).__name__); _redis = False
    return _redis or None

def enqueue(db, kind, payload, user_id=None, dedupe_key=None, delay_s=0, max_attempts=4):
    """Returns the job, or None when an identical active job (same dedupe_key) already exists.
    dedupe_key is unique while the job is pending/running and cleared when it finishes."""
    from sqlalchemy.exc import IntegrityError
    if dedupe_key and db.scalar(select(AgentJob).where(AgentJob.dedupe_key == dedupe_key)): return None
    j = AgentJob(kind=kind, payload=payload, user_id=user_id, run_after=_now() + dt.timedelta(seconds=delay_s), max_attempts=max_attempts, dedupe_key=dedupe_key)
    db.add(j)
    try: db.commit()
    except IntegrityError: db.rollback(); return None
    r = _r()
    if r:
        try: r.lpush("sniper:jobs", j.id)
        except Exception: pass
    return j

def claim(db):
    j = db.scalar(select(AgentJob).where(AgentJob.status == "pending", AgentJob.run_after <= _now()).order_by(AgentJob.run_after).limit(1))
    if not j: return None
    n = db.execute(update(AgentJob).where(AgentJob.id == j.id, AgentJob.status == "pending").values(status="running", attempts=j.attempts + 1)).rowcount
    db.commit()
    if n != 1: return None  # another worker won the race
    db.refresh(j); return j

def run_once(db, handlers: dict) -> bool:
    """Process one job. Retries with exponential backoff; moves to 'dead' (dead-letter) after max_attempts."""
    import time
    j = claim(db)
    if not j: return False
    t = time.perf_counter()
    db.add(AgentEvent(agent=j.kind, event="started", job_id=j.id)); db.commit()
    try:
        handlers[j.kind](db, j)
        j.status, j.finished_at, j.dedupe_key = "done", _now(), None
        db.add(AgentEvent(agent=j.kind, event="completed", job_id=j.id, duration_ms=(time.perf_counter() - t) * 1000))
    except Exception as e:
        db.rollback(); j = db.get(AgentJob, j.id); msg = f"{type(e).__name__}: {str(e)[:200]}"
        j.last_error = msg
        if j.attempts >= j.max_attempts: j.status, j.finished_at, j.dedupe_key = "dead", _now(), None
        else: j.status, j.run_after = "pending", _now() + dt.timedelta(seconds=min(3600, 30 * 2 ** j.attempts))
        db.add(AgentEvent(agent=j.kind, event="failed", job_id=j.id, duration_ms=(time.perf_counter() - t) * 1000, detail=msg))
    db.commit(); return True

def stats(db):
    from sqlalchemy import func
    return {s: n for s, n in db.execute(select(AgentJob.status, func.count()).group_by(AgentJob.status))}
