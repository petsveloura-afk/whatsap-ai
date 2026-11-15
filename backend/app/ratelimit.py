"""Tiny in-memory sliding-window rate limiter (free, single-instance)."""
import time, collections
class Limiter:
    def __init__(s): s.hits = collections.defaultdict(collections.deque)
    def allow(s, key: str, limit: int, window: float) -> bool:
        now = time.monotonic(); q = s.hits[key]
        while q and now - q[0] > window: q.popleft()
        if len(q) >= limit: return False
        q.append(now); return True
limiter = Limiter()
