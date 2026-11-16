"""Scout sources, job queue/worker, notifications, profile, admin center, feature flags, roles.
Imported at the bottom of main.py (shares its auth/pipeline helpers)."""
import asyncio, datetime as dt, logging, os, time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db, SessionLocal
from .models import User, SearchConfig, Listing, Subscription, AuditLog
from .models2 import (DataSource, IngestionEvent, ListingImage, AgentJob, AgentEvent, Notification, NotificationPreference,
                      UserProfile, AdminAction, Role, Permission)
from . import flags, jobqueue, scout
from .main import current_user, need, pipeline, audit, _own_search, PLANS
from fastapi import HTTPException as HE

router = APIRouter()
log = logging.getLogger("sniper")
ADMIN = ("admin", "super_admin")
STAFF = ("support", "admin", "super_admin")
ROLE_PERMS = {"user": ["own_data"], "support": ["own_data", "read_users", "read_audit"],
              "admin": ["own_data", "read_users", "read_audit", "write_users", "read_system", "write_flags"],
              "super_admin": ["own_data", "read_users", "read_audit", "write_users", "read_system", "write_flags", "change_roles"]}
def _now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

# ---------- Scout sources ----------
class SrcIn(BaseModel):
    search_id: str
    kind: str = Field(pattern="^(rss|jsonfeed|jsonld|csv|reddit|tgpublic)$")
    url: str = Field(max_length=1000)
    interval_minutes: int = Field(30, ge=15, le=1440)
MAX_SOURCES = 10
def _own_src(db, u, sid) -> DataSource:
    s = db.get(DataSource, sid)
    if not s or s.user_id != u.id: raise HTTPException(404, "Source not found")
    return s
@router.post("/api/sources", status_code=201)
def src_add(b: SrcIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_search(db, u, b.search_id)
    if db.scalar(select(func.count()).select_from(DataSource).where(DataSource.user_id == u.id)) >= MAX_SOURCES: raise HTTPException(402, "Source limit reached")
    try: url = scout.check_url(b.url)
    except scout.UnsafeURL as e: raise HTTPException(400, str(e))
    s = DataSource(user_id=u.id, search_id=b.search_id, kind=b.kind, url=url, interval_minutes=b.interval_minutes); db.add(s); db.commit()
    return {"id": s.id}
def _src_row(s): return {"id": s.id, "search_id": s.search_id, "kind": s.kind, "url": s.url, "interval_minutes": s.interval_minutes, "active": s.active,
                         "status": s.status, "last_error": s.last_error, "last_polled_at": str(s.last_polled_at) if s.last_polled_at else None}
@router.get("/api/sources")
def src_list(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_src_row(s) for s in db.scalars(select(DataSource).where(DataSource.user_id == u.id))]
@router.delete("/api/sources/{sid}", status_code=204)
def src_del(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_src(db, u, sid); db.delete(s); db.commit()
@router.post("/api/sources/{sid}/poll", status_code=202)
def src_poll(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_src(db, u, sid)
    j = jobqueue.enqueue(db, "poll_source", {"source_id": s.id}, user_id=u.id, dedupe_key="poll:" + s.id)
    return {"queued": j is not None, "note": None if j else "A poll for this source is already queued"}
@router.get("/api/sources/{sid}/events")
def src_events(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_src(db, u, sid)
    rows = db.scalars(select(IngestionEvent).where(IngestionEvent.source_id == sid, IngestionEvent.user_id == u.id).order_by(IngestionEvent.created_at.desc()).limit(50))
    return [{"status": e.status, "detail": e.detail, "latency_ms": e.latency_ms, "at": str(e.created_at)} for e in rows]

def _robots_fetch(client):
    def f(url):
        try:
            scout.check_url(url); r = client.get(url, headers={"User-Agent": scout.UA}, follow_redirects=False, timeout=10)
            return r.text if r.status_code == 200 else None
        except Exception: return None
    return f
def handle_poll(db: Session, job: AgentJob, client=None):
    """Job handler. Raises on failure so the queue retries with backoff / dead-letters."""
    import httpx
    src = db.get(DataSource, job.payload.get("source_id"))
    if not src or not src.active: return
    u, cfg = db.get(User, src.user_id), db.get(SearchConfig, src.search_id)
    if not u or not u.is_active or not cfg or cfg.deleted_at or not cfg.active: return
    own = client is None; client = client or httpx.Client()
    t = time.perf_counter()
    try:
        if not scout.robots_allows(src.url, _robots_fetch(client)): raise PermissionError("blocked by robots.txt")
        items = scout.ADAPTERS[src.kind](scout.fetch(src.url, client))[:30]
        new = dup = low = 0
        for it in items:
            text = scout.listing_text(it)
            if len(text) < 5: continue
            try:
                l = pipeline(db, u, cfg, text, it.get("link"))
                new += l.status == "new"; low += l.status != "new"
                if it.get("image") and it["image"].startswith("https://"): db.add(ListingImage(listing_id=l.id, url=it["image"][:1000])); db.commit()
            except HE as e:
                if e.status_code == 409: dup += 1
                else: raise
        src.status, src.last_error, src.last_polled_at = "OK", None, _now()
        db.add(IngestionEvent(user_id=u.id, source_id=src.id, channel=src.kind, status="ok", detail=f"items={len(items)} new={new} filtered={low} duplicates={dup}", latency_ms=(time.perf_counter() - t) * 1000))
        db.commit()
    except Exception as e:
        db.rollback(); src = db.get(DataSource, src.id)
        src.status, src.last_error, src.last_polled_at = "ERROR", f"{type(e).__name__}: {str(e)[:200]}", _now()
        db.add(IngestionEvent(user_id=src.user_id, source_id=src.id, channel=src.kind, status="error", detail=src.last_error, latency_ms=(time.perf_counter() - t) * 1000))
        db.commit(); raise
    finally:
        if own: client.close()
HANDLERS = {"poll_source": handle_poll}

def schedule_due(db: Session) -> int:
    n = 0
    for s in db.scalars(select(DataSource).where(DataSource.active)):
        if s.last_polled_at is None or _now() - s.last_polled_at.replace(tzinfo=None) >= dt.timedelta(minutes=s.interval_minutes):
            n += jobqueue.enqueue(db, "poll_source", {"source_id": s.id}, user_id=s.user_id, dedupe_key="poll:" + s.id) is not None
    return n

_tasks: list = []
async def _worker():
    while True:
        busy = False
        try:
            def step():
                with SessionLocal() as db: return jobqueue.run_once(db, HANDLERS)
            busy = await asyncio.to_thread(step)
        except Exception as e: log.warning("worker error: %s", type(e).__name__)
        if not busy:
            r = jobqueue._r()
            if r: await asyncio.to_thread(lambda: r.blpop("sniper:jobs", timeout=5))
            else: await asyncio.sleep(3)
async def _scheduler():
    while True:
        try:
            def step():
                with SessionLocal() as db: return schedule_due(db)
            await asyncio.to_thread(step)
        except Exception as e: log.warning("scheduler error: %s", type(e).__name__)
        await asyncio.sleep(60)
async def start_workers():
    if os.environ.get("WORKER_ENABLED") == "1" and not _tasks:
        _tasks.extend([asyncio.create_task(_worker()), asyncio.create_task(_scheduler())])
async def stop_workers():
    for t in _tasks: t.cancel()
    _tasks.clear()

# ---------- notifications / profile ----------
@router.get("/api/notifications")
def notif_list(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == u.id).order_by(Notification.created_at.desc()).limit(100)).all()
    return {"unread": sum(not n.read for n in rows), "items": [{"id": n.id, "title": n.title, "body": n.body, "listing_id": n.listing_id, "read": n.read, "at": str(n.created_at)} for n in rows]}
@router.post("/api/notifications/{nid}/read")
def notif_read(nid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != u.id: raise HTTPException(404, "Notification not found")
    n.read = True; db.commit(); return {"ok": True}
class NPrefIn(BaseModel):
    in_app: bool = True
    min_score: int = Field(60, ge=0, le=100)
@router.get("/api/notifications/preferences")
def npref_get(u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == u.id)); return {"in_app": p.in_app if p else True, "min_score": p.min_score if p else 60}
@router.put("/api/notifications/preferences")
def npref_put(b: NPrefIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == u.id)) or NotificationPreference(user_id=u.id)
    p.in_app, p.min_score = b.in_app, b.min_score; db.add(p); db.commit(); return b.model_dump()
class ProfIn(BaseModel):
    display_name: str | None = Field(None, max_length=80)
    locale: str = Field("he", pattern="^(he|en)$")
    timezone: str = Field("Asia/Jerusalem", max_length=50)
@router.get("/api/me/profile")
def prof_get(u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(UserProfile).where(UserProfile.user_id == u.id)); return {"display_name": p.display_name if p else None, "locale": p.locale if p else "he", "timezone": p.timezone if p else "Asia/Jerusalem"}
@router.put("/api/me/profile")
def prof_put(b: ProfIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(UserProfile).where(UserProfile.user_id == u.id)) or UserProfile(user_id=u.id)
    p.display_name, p.locale, p.timezone = b.display_name, b.locale, b.timezone; db.add(p); db.commit(); return b.model_dump()

# ---------- agents / queues ----------
@router.get("/api/agents/events")
def agent_events(u: User = Depends(need(*STAFF)), db: Session = Depends(get_db)):
    return [{"agent": e.agent, "event": e.event, "job_id": e.job_id, "duration_ms": e.duration_ms, "detail": e.detail, "at": str(e.created_at)}
            for e in db.scalars(select(AgentEvent).order_by(AgentEvent.created_at.desc()).limit(100))]

# ---------- admin center ----------
@router.get("/api/admin/overview")
def admin_overview(a: User = Depends(need(*STAFF)), db: Session = Depends(get_db)):
    cnt = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))
    active = db.scalars(select(Subscription).where(Subscription.status == "active")).all()
    return {"users": cnt(select(User)), "disabled_users": cnt(select(User).where(User.is_active.is_(False))),
            "active_subscriptions": len(active), "mrr_ils": sum(PLANS[s.plan]["price"] for s in active if s.plan in PLANS),
            "active_searches": cnt(select(SearchConfig).where(SearchConfig.active, SearchConfig.deleted_at.is_(None))),
            "listings": cnt(select(Listing)), "sources": cnt(select(DataSource)), "sources_in_error": cnt(select(DataSource).where(DataSource.status == "ERROR")),
            "queue": jobqueue.stats(db), "flags": flags.load(db)}
@router.get("/api/admin/subscriptions")
def admin_subs(a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    return [{"user_id": s.user_id, "plan": s.plan, "status": s.status} for s in db.scalars(select(Subscription))]
@router.get("/api/admin/sources")
def admin_sources(a: User = Depends(need(*STAFF)), db: Session = Depends(get_db)):
    return [{**_src_row(s), "user_id": s.user_id} for s in db.scalars(select(DataSource).limit(500))]
@router.get("/api/admin/jobs")
def admin_jobs(status: str | None = None, a: User = Depends(need(*STAFF)), db: Session = Depends(get_db)):
    q = select(AgentJob).order_by(AgentJob.created_at.desc()).limit(100)
    if status: q = q.where(AgentJob.status == status)
    return [{"id": j.id, "kind": j.kind, "status": j.status, "attempts": j.attempts, "last_error": j.last_error, "at": str(j.created_at)} for j in db.scalars(q)]
@router.post("/api/admin/jobs/{jid}/retry")
def admin_job_retry(jid: str, a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    j = db.get(AgentJob, jid)
    if not j or j.status != "dead": raise HTTPException(404, "No dead job with this id")
    j.status, j.attempts, j.run_after = "pending", 0, _now()
    audit(db, a, "admin.job.retry", jid); db.add(AdminAction(admin_id=a.id, action="job.retry", target=jid)); db.commit(); return {"ok": True}
@router.get("/api/admin/actions")
def admin_actions(a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    return [{"admin": x.admin_id, "action": x.action, "target": x.target, "detail": x.detail, "at": str(x.created_at)} for x in db.scalars(select(AdminAction).order_by(AdminAction.created_at.desc()).limit(200))]
@router.get("/api/admin/roles")
def admin_roles(a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    if not db.scalar(select(func.count()).select_from(Role)):
        for r, ps in ROLE_PERMS.items():
            db.add(Role(name=r)); [db.add(Permission(role=r, permission=p)) for p in ps]
        db.commit()
    return {r: [p.permission for p in db.scalars(select(Permission).where(Permission.role == r))] for r in ROLE_PERMS}
class FlagsIn(BaseModel): flags: dict[str, bool]
def _caps(): 
    from . import llm, brains, discovery
    return {"llm_configured": llm.configured(), "pgvector_env": os.environ.get("USE_PGVECTOR") == "1",
            "brains": brains.status()["active"], "web_search": discovery.providers()}
@router.get("/api/admin/system-settings")
def sys_get(a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    return {"flags": flags.load(db, True), "capabilities": _caps()}
@router.patch("/api/admin/system-settings")
def sys_patch(b: FlagsIn, a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    try: new = flags.save(db, b.flags)
    except ValueError as e: raise HTTPException(400, str(e))
    audit(db, a, "admin.flags", None, b.flags); db.add(AdminAction(admin_id=a.id, action="flags.change", detail=b.flags)); db.commit()
    return {"flags": new, "capabilities": _caps()}
async def maintenance(request: Request, call_next):
    """When maintenance_mode is on, block writes except auth/admin/webhooks."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.url.path.startswith(("/api/auth", "/api/admin", "/api/webhooks")):
        with SessionLocal() as db: on = flags.load(db)["maintenance_mode"]
        if on: return JSONResponse({"detail": "Maintenance mode"}, status_code=503)
    return await call_next(request)
