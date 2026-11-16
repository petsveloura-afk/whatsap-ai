"""Key pool (v3.7): shared plumbing for every free provider (LLM brains and web-search engines).

* Several keys per provider: NAME=k1,k2,k3 (comma / space / newline separated) and/or NAME_2, NAME_3 ... NAME_9.
  More keys = more free quota, because free tiers are limited per key.
* Round-robin rotation so load is spread over the keys.
* Cooldowns: a key (or key+model) that hit a rate limit / daily quota / auth error is skipped for a while instead of being
  hammered on every request; it comes back automatically.
* Nothing here ever returns or logs a key. Only a short non-reversible fingerprint is exposed in status screens.
Pure python, no network, thread-safe.
"""
import hashlib, os, re, threading, time

_LOCK = threading.RLock()
_STATE: dict[str, dict] = {}     # id -> {"until": monotonic, "err": str}
_RR: dict[str, int] = {}         # name -> rotating counter
_STATS: dict[str, dict] = {}     # name -> counters for the status screen

_SPLIT = re.compile(r"[,\s;]+")
_DAILY = re.compile(r"per\s*day|daily|quota|exhaust|RPD|TPD|insufficient|billing|credit|limit\s*exceeded.*(day|month)|monthly", re.I)


def keys(*names: str) -> list[str]:
    """All distinct keys found in the given env var names (each may hold several keys, plus NAME_2..NAME_9)."""
    out: list[str] = []
    for n in names:
        raws = [os.environ.get(n, "")] + [os.environ.get(f"{n}_{i}", "") for i in range(2, 10)]
        for raw in raws:
            for k in _SPLIT.split(raw.strip()):
                if k and k not in out: out.append(k)
    return out


def fp(key: str | None) -> str:
    """Short fingerprint for logs/status. Not reversible."""
    return hashlib.sha256((key or "-").encode()).hexdigest()[:6]


def rotate(name: str, items: list) -> list:
    """Items starting from the next round-robin position (each call advances by one)."""
    if len(items) < 2: return list(items)
    with _LOCK:
        i = _RR.get(name, 0) % len(items); _RR[name] = i + 1
    return items[i:] + items[:i]


def available(ident: str) -> bool:
    with _LOCK:
        s = _STATE.get(ident)
        return not s or s["until"] <= time.monotonic()


def cool(ident: str, seconds: float, err: str = ""):
    with _LOCK: _STATE[ident] = {"until": time.monotonic() + max(1.0, seconds), "err": err[:200]}


def remaining(ident: str) -> int:
    with _LOCK:
        s = _STATE.get(ident)
        return max(0, int(s["until"] - time.monotonic())) if s else 0


def clear(ident: str | None = None):
    with _LOCK:
        if ident is None: _STATE.clear(); _STATS.clear(); _RR.clear()
        else: _STATE.pop(ident, None)


def cooling(prefix: str) -> int:
    """How many ids starting with prefix are cooling down right now."""
    now = time.monotonic()
    with _LOCK: return sum(1 for k, s in _STATE.items() if k.startswith(prefix) and s["until"] > now)


def cooldown_for(status: int | None, body: str = "", retry_after: float | None = None) -> float:
    """How long to leave a key alone after an HTTP error. Daily/monthly quota errors wait long, short rate limits wait briefly."""
    if status in (401,): return 6 * 3600          # bad / revoked key
    if status in (402,): return 6 * 3600          # needs payment: never retry automatically
    if status in (403,): return 3600
    if status == 429:
        if _DAILY.search(body or ""): return 3600
        return min(300.0, max(15.0, retry_after or 60.0))
    return 30.0                                    # 5xx, timeouts, network


def redact(text: str, *secrets: str) -> str:
    t = str(text or "")
    for s in secrets:
        if s and len(s) >= 4: t = t.replace(s, "***")
    return re.sub(r"(?i)(bearer\s+|key=|api[_-]?key[\"':= ]+)[A-Za-z0-9_\-\.]{8,}", r"\1***", t)[:300]


def record(name: str, ok: bool, err: str = "", ms: float = 0.0, model: str | None = None):
    with _LOCK:
        s = _STATS.setdefault(name, {"ok": 0, "fail": 0, "last_error": None, "last_ok": None, "last_model": None, "avg_ms": None})
        if ok:
            s["ok"] += 1; s["last_ok"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()); s["last_model"] = model or s["last_model"]
            s["avg_ms"] = round(ms if s["avg_ms"] is None else 0.8 * s["avg_ms"] + 0.2 * ms)
        else:
            s["fail"] += 1; s["last_error"] = err[:200]


def stats(name: str) -> dict:
    with _LOCK: return dict(_STATS.get(name) or {"ok": 0, "fail": 0, "last_error": None, "last_ok": None, "last_model": None, "avg_ms": None})
