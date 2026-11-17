"""v3.16: rich user profile, learned-memory sync and a wiring self-check (additive, no new tables).
Registered at the bottom of main.py inside try/except, so a problem here can never take the core API down.

GET  /api/profile              the user's profile: identity, plan and quota, stats, learned taste, memory, completeness score + next steps
POST /api/profile/sync-memory  turns what the user actually saved / contacted / rejected into long-term agent memories (idempotent, honours the privacy switch)
DELETE /api/integrations/whatsapp/consent  withdraw WhatsApp consent without retyping the number
GET  /api/admin/diagnostics    (staff) one call that answers "is everything connected?": database, tables, migration head, routes, brains, queue, flags
Everything is scoped to the logged-in user; nothing is deleted or modified except the memories the user explicitly asks to sync.
"""
import datetime as dt, logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session
from . import agent, brain_plus as BP, brains, flags, jobqueue
from . import main as _m
from .db import Base, engine, get_db
from .main import current_user, need
from .models import Listing, SearchConfig, TelegramSource, User
from .models_agent import AgentMemory
from .routes_v2 import STAFF

router = APIRouter(); log = logging.getLogger("sniper")
ROW_CAP = 500   # newest listings that feed the taste profile (bounded work per request)


def _rows(db: Session, uid: str) -> list[dict]:
    q = select(Listing.status, Listing.score, Listing.extracted).where(Listing.user_id == uid).order_by(Listing.created_at.desc()).limit(ROW_CAP)
    return [{"status": s, "score": sc, "extracted": ex or {}} for s, sc, ex in db.execute(q)]


def _naive_days(t) -> int:
    if t is None: return 0
    t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    return max(0, (dt.datetime.now(dt.timezone.utc) - t).days)


def _mask(n: str | None) -> str | None:
    """Last four digits only: enough for the user to recognise the number, never the whole of it."""
    return ("•••• " + n[-4:]) if n and len(n) >= 4 else None


@router.get("/api/profile")
def profile(u: User = Depends(current_user), db: Session = Depends(get_db)):
    by = {s: (n, a, mx) for s, n, a, mx in db.execute(select(Listing.status, func.count(), func.avg(Listing.score), func.max(Listing.score)).where(Listing.user_id == u.id).group_by(Listing.status))}
    cnt = lambda k: by.get(k, (0, 0, 0))[0]
    total = sum(v[0] for v in by.values())
    avg = round(sum((v[1] or 0) * v[0] for v in by.values()) / total, 1) if total else None
    best = max((v[2] or 0 for v in by.values()), default=None) if total else None
    searches = db.scalar(select(func.count()).select_from(SearchConfig).where(SearchConfig.user_id == u.id, SearchConfig.deleted_at.is_(None))) or 0
    plan = _m._plan(db, u); cap = _m.search_cap(db, u)
    mems = db.scalars(select(AgentMemory.text).where(AgentMemory.user_id == u.id)).all()
    learned = sum(1 for t in mems if t.startswith(BP.LEARNED_PREFIX))
    pers = bool(_m._personalization_on(db, u))
    tele = bool(db.scalar(select(func.count()).select_from(TelegramSource).where(TelegramSource.user_id == u.id, TelegramSource.chat_id.is_not(None))))
    ins = BP.insights(_rows(db, u.id))
    facts = {"searches": searches, "listings": total, "saved": cnt("saved") + cnt("contacted") + cnt("purchased"), "rejected": cnt("rejected"),
             "memories": len(mems), "personalization": pers, "whatsapp_consent": bool(u.whatsapp_consent), "telegram": tele}
    return {
        "user": {"id": u.id, "email": u.email, "role": u.role, "initials": BP.initials(u.email), "member_days": _naive_days(u.created_at),
                 "member_since": u.created_at.date().isoformat() if u.created_at else None},
        "plan": {"id": plan, "price": _m.PLANS.get(plan, {}).get("price", 0), "max_searches": cap if cap < 10**6 else None, "searches_used": searches},
        "stats": {"searches": searches, "listings": total, "new": cnt("new"), "saved": cnt("saved"), "contacted": cnt("contacted"), "purchased": cnt("purchased"),
                  "rejected": cnt("rejected"), "avg_score": avg, "best_score": best},
        "insights": {**ins, "statements": BP.memory_statements(ins)},
        "memory": {"agent": len(mems), "learned": learned, "personalization": pers},
        "contact": {"whatsapp_consent": bool(u.whatsapp_consent), "whatsapp_masked": _mask(u.whatsapp_number), "telegram_linked": tele},
        "completeness": BP.completeness(facts),
    }


@router.delete("/api/integrations/whatsapp/consent")
def wa_revoke(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Withdraw WhatsApp consent in one call (the existing PUT needs the full number again). Idempotent. The stored number is kept so the user can re-enable."""
    u.whatsapp_consent = False; db.commit(); return {"consent": False}


@router.post("/api/profile/sync-memory")
def sync_memory(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Idempotent: remember() already skips near-duplicates, so pressing the button twice never doubles anything."""
    if not _m._personalization_on(db, u): raise HTTPException(409, "הזיכרון כבוי אצלך (פרטיות). אפשר להפעיל אותו בהגדרות הזיכרון.")
    ins = BP.insights(_rows(db, u.id)); stmts = BP.memory_statements(ins)
    if not stmts: return {"added": 0, "known": 0, "statements": [], "message": "עוד אין מספיק מידע. שמור או דחה כמה מודעות והמערכת תלמד מהן.", "confidence": ins["confidence"]}
    added, known = 0, 0
    for s in stmts:
        r = agent.remember(db, u, s, "preference")
        if r.get("saved"): added += 1
        else: known += 1
    return {"added": added, "known": known, "statements": stmts, "confidence": ins["confidence"],
            "message": f"נוספו {added} זיכרונות חדשים" + (f", {known} כבר היו ידועים" if known else "") + "."}


@router.get("/api/admin/diagnostics")
def diagnostics(a: User = Depends(need(*STAFF)), db: Session = Depends(get_db)):
    """Read-only self-check. Every probe is isolated: one failing probe is reported, never raised."""
    checks: list[dict] = []
    def probe(name, fn):
        try:
            ok, detail = fn(); checks.append({"name": name, "ok": bool(ok), "detail": detail})
        except Exception as e:
            checks.append({"name": name, "ok": False, "detail": type(e).__name__ + ": " + str(e)[:160]})
    probe("database", lambda: (db.execute(text("select 1")).scalar() == 1, engine.dialect.name))
    def tables():
        have = set(inspect(engine).get_table_names()); want = set(Base.metadata.tables); miss = sorted(want - have)
        return (not miss, f"{len(want) - len(miss)}/{len(want)} tables" + (f", missing: {', '.join(miss[:8])}" if miss else ""))
    probe("tables", tables)
    def migration():
        from alembic.config import Config; from alembic.script import ScriptDirectory
        import os
        ini = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
        head = ScriptDirectory.from_config(Config(ini)).get_heads()
        if "alembic_version" not in inspect(engine).get_table_names(): return True, f"no alembic_version table (dev/test database); code head {head[0]}"
        cur = db.execute(text("select version_num from alembic_version")).scalar()
        return cur in head, f"db={cur} head={head[0]}"
    probe("migrations", migration)
    def routes():
        paths = {r.path for r in _m.app.routes}; need_ = ["/api/profile", "/api/agent/chat", "/api/pro/catalog", "/api/scan/start", "/api/listings", "/api/searches", "/api/memory"]
        miss = [p for p in need_ if p not in paths]
        return (not miss, f"{len(paths)} paths" + (f", missing: {', '.join(miss)}" if miss else ""))
    probe("routes", routes)
    probe("agent_memory", lambda: (True, f"{db.scalar(select(func.count()).select_from(AgentMemory)) or 0} rows"))
    probe("queue", lambda: (True, jobqueue.stats(db)))
    def br():
        s = brains.status(); act = s.get("active") or []
        return (True, f"{len(act)} active brain(s)" if act else "no AI key configured (rules mode, still fully functional)")
    probe("brains", br)
    probe("flags", lambda: (True, flags.load(db)))
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
