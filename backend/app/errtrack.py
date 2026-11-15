"""Self-hosted error tracking (free): groups errors by fingerprint into error_events, scrubs secrets, shows in admin.
Optional: if SENTRY_DSN is set AND sentry-sdk is installed, errors are also forwarded (Sentry has a free tier; off by default)."""
import hashlib, os, re, traceback, datetime as dt, logging
from sqlalchemy import select
from .models3 import ErrorEvent
log = logging.getLogger("sniper")
_SECRET = re.compile(r"(?i)(bearer\s+[\w\.\-]+|password[\"'=:\s]+[^\s,\"']+|secret[\"'=:\s]+[^\s,\"']+|token[\"'=:\s]+[^\s,\"']+|ssk_[\w]+|eyJ[\w\-\.]{20,})")
def scrub(s: str) -> str: return _SECRET.sub("[redacted]", s or "")
def _now(): return dt.datetime.now(dt.timezone.utc)

def fingerprint(exc: BaseException, where: str) -> str:
    tb = traceback.extract_tb(exc.__traceback__); last = f"{tb[-1].filename.rsplit('/', 1)[-1]}:{tb[-1].name}" if tb else ""
    return hashlib.sha1(f"{type(exc).__name__}|{last}|{where}".encode()).hexdigest()[:40]

def capture(db, exc: BaseException, where: str = "") -> ErrorEvent | None:
    """Never raises: error tracking must not cause errors."""
    try:
        fp = fingerprint(exc, where); row = db.scalar(select(ErrorEvent).where(ErrorEvent.fingerprint == fp))
        if row: row.count += 1; row.last_seen = _now(); row.resolved = False
        else:
            row = ErrorEvent(fingerprint=fp, kind=type(exc).__name__, message=scrub(str(exc))[:300], route=scrub(where)[:200],
                             sample=scrub("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-3000:]))
            db.add(row)
        db.commit()
        _sentry(exc)
        return row
    except Exception as e:
        try: db.rollback()
        except Exception: pass
        log.warning("error tracking failed: %s", type(e).__name__); return None

_sentry_ready = None
def _sentry(exc):
    global _sentry_ready
    if not os.environ.get("SENTRY_DSN"): return
    try:
        import sentry_sdk
        if _sentry_ready is None: sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], send_default_pii=False, traces_sample_rate=0); _sentry_ready = True
        sentry_sdk.capture_exception(exc)
    except Exception: _sentry_ready = False
