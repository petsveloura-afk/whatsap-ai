"""Shared (multi-instance) sliding-window rate limiter stored in the existing database (free; no Redis).
Drop-in for ratelimit.Limiter: allow(key, limit, window). Falls back to the in-memory limiter if the DB is unreachable
(fail-open for availability, logged). Old rows are pruned opportunistically and by the worker housekeeping."""
import time, logging
from sqlalchemy import select, func, delete
from .db import SessionLocal
from .models3 import RateHit
from .ratelimit import Limiter
log = logging.getLogger("sniper")

class SharedLimiter:
    def __init__(s, session_factory=None): s.sf = session_factory or SessionLocal; s.local = Limiter()
    def allow(s, key: str, limit: int, window: float) -> bool:
        now = time.time()
        try:
            with s.sf() as db:
                n = db.scalar(select(func.count()).select_from(RateHit).where(RateHit.key == key, RateHit.at > now - window))
                if n >= limit: return False
                db.add(RateHit(key=key[:200], at=now)); db.commit(); return True
        except Exception as e:
            log.warning("shared rate limit unavailable (%s); using in-memory", type(e).__name__)
            return s.local.allow(key, limit, window)

def prune(db, older_than_s: float = 3600) -> int:
    return db.execute(delete(RateHit).where(RateHit.at < time.time() - older_than_s)).rowcount
