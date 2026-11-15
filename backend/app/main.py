import asyncio, hashlib, hmac, os, secrets, time, uuid, datetime as dt
from fastapi import FastAPI, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base, engine, get_db
from .models import User, SearchConfig, Listing, AuditLog, TelegramSource
from .events import hub, STATS
from .security import hash_pw, check_pw, make_token, read_token
from .extract import extract
from .scoring import score, risks
app = FastAPI(title="Smart Sniper AI", version="3.0.0-core")
if os.environ.get("AUTO_CREATE_TABLES") == "1": Base.metadata.create_all(engine)  # dev/tests only; production uses Alembic
def current_user(authorization: str = Header(""), db: Session = Depends(get_db)) -> User:
    try: uid = read_token(authorization.removeprefix("Bearer "))
    except Exception: raise HTTPException(401, "Invalid or expired token")
    u = db.get(User, uid)
    if not u or not u.is_active: raise HTTPException(401, "Unknown or disabled user")
    return u
class Cred(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
@app.get("/api/health")
def health(): return {"status": "ok"}
@app.post("/api/auth/register", status_code=201)
def register(c: Cred, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == c.email.lower())): raise HTTPException(409, "Email already registered")
    boot = [e.strip().lower() for e in os.environ.get("SUPER_ADMIN_EMAILS", "").split(",") if e.strip()]
    u = User(email=c.email.lower(), password_hash=hash_pw(c.password), role="super_admin" if c.email.lower() in boot else "user"); db.add(u); db.commit()
    return {"id": u.id, "email": u.email}
@app.post("/api/auth/login")
def login(c: Cred, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == c.email.lower()))
    if not u or not check_pw(c.password, u.password_hash): raise HTTPException(401, "Invalid credentials")
    return {"access_token": make_token(u.id), "token_type": "bearer"}
@app.get("/api/auth/me")
def me(u: User = Depends(current_user)): return {"id": u.id, "email": u.email, "role": u.role}
class SearchIn(BaseModel):
    name: str
    category: str
    location: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    required_keywords: list[str] = []
    excluded_keywords: list[str] = []
    min_score: int = Field(60, ge=0, le=100)
    weights: dict[str, float] | None = None
def _own_search(db, u, sid) -> SearchConfig:
    s = db.get(SearchConfig, sid)
    if not s or s.user_id != u.id or s.deleted_at: raise HTTPException(404, "Search not found")
    return s
@app.post("/api/searches", status_code=201)
def create_search(b: SearchIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = SearchConfig(user_id=u.id, **b.model_dump()); db.add(s); db.commit(); return {"id": s.id}
@app.get("/api/searches")
def list_searches(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SearchConfig).where(SearchConfig.user_id == u.id, SearchConfig.deleted_at.is_(None))).all()
    return [{"id": s.id, "name": s.name, "active": s.active, "category": s.category} for s in rows]
@app.post("/api/searches/{sid}/pause")
def pause(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, sid); s.active = False; db.commit(); return {"active": False}
@app.post("/api/searches/{sid}/resume")
def resume(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, sid); s.active = True; db.commit(); return {"active": True}
@app.delete("/api/searches/{sid}", status_code=204)
def delete(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, sid); s.deleted_at = dt.datetime.now(dt.timezone.utc); db.commit()
class IngestIn(BaseModel):
    search_id: str
    text: str = Field(min_length=5, max_length=5000)
    source_url: str | None = None
@app.post("/api/listings/ingest", status_code=201)
def ingest(b: IngestIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Real pipeline for user-provided listing text: extract -> dedup -> risk -> score."""
    s = _own_search(db, u, b.search_id)
    if not s.active: raise HTTPException(409, "Search is paused")
    l = pipeline(db, u, s, b.text, b.source_url)
    return {"id": l.id, "status": l.status, "score": l.score, "extracted": l.extracted, "detail": l.score_detail, "risks": l.risks}
@app.get("/api/listings")
def listings(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.score.desc())).all()
    return [{"id": l.id, "score": l.score, "status": l.status, "extracted": l.extracted, "risks": l.risks} for l in rows]

def audit(db, actor, action, target=None, detail=None):
    db.add(AuditLog(actor_id=actor.id if actor else None, action=action, target=target, detail=detail))
def need(*roles):
    def dep(u: User = Depends(current_user)) -> User:
        if u.role not in roles: raise HTTPException(403, "Forbidden")
        return u
    return dep
class SearchPatch(BaseModel):
    name: str | None = None
    location: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    required_keywords: list[str] | None = None
    excluded_keywords: list[str] | None = None
    min_score: int | None = Field(None, ge=0, le=100)
    weights: dict[str, float] | None = None
@app.get("/api/searches/{sid}")
def get_search(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, sid)
    return {c.name: getattr(s, c.name) for c in s.__table__.columns if c.name != "user_id"}
@app.patch("/api/searches/{sid}")
def patch_search(sid: str, b: SearchPatch, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, sid)
    for k, v in b.model_dump(exclude_unset=True).items(): setattr(s, k, v)
    db.commit(); return {"id": s.id}
def _own_listing(db, u, lid) -> Listing:
    l = db.get(Listing, lid)
    if not l or l.user_id != u.id: raise HTTPException(404, "Listing not found")
    return l
def _set_status(status):
    def h(lid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
        l = _own_listing(db, u, lid); l.status = status; db.commit(); return {"id": l.id, "status": status}
    return h
for _n, _s in (("save", "saved"), ("reject", "rejected"), ("contacted", "contacted"), ("purchased", "purchased")):
    app.post(f"/api/listings/{{lid}}/{_n}")(_set_status(_s))
class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)
    note: str | None = Field(None, max_length=2000)
@app.post("/api/listings/{lid}/feedback")
def feedback(lid: str, b: FeedbackIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    l = _own_listing(db, u, lid); l.feedback = {"rating": b.rating, "comment": b.comment}
    if b.note is not None: l.note = b.note
    db.commit(); return {"ok": True}
@app.get("/api/me/export")
def export(u: User = Depends(current_user), db: Session = Depends(get_db)):
    cols = lambda o: {c.name: str(getattr(o, c.name)) if isinstance(getattr(o, c.name), dt.datetime) else getattr(o, c.name) for c in o.__table__.columns}
    return {"user": {"id": u.id, "email": u.email, "role": u.role},
            "searches": [cols(x) for x in db.scalars(select(SearchConfig).where(SearchConfig.user_id == u.id))],
            "listings": [cols(x) for x in db.scalars(select(Listing).where(Listing.user_id == u.id))]}
@app.delete("/api/me", status_code=204)
def delete_me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for M in (Listing, SearchConfig):
        for x in db.scalars(select(M).where(M.user_id == u.id)): db.delete(x)
    audit(db, u, "account.deleted", u.id); db.delete(u); db.commit()
@app.get("/api/admin/users")
def admin_users(a: User = Depends(need("support", "admin", "super_admin")), db: Session = Depends(get_db)):
    return [{"id": x.id, "email": x.email, "role": x.role, "is_active": x.is_active} for x in db.scalars(select(User))]
class UserPatch(BaseModel):
    role: str | None = Field(None, pattern="^(user|support|admin|super_admin)$")
    is_active: bool | None = None
@app.patch("/api/admin/users/{uid}")
def admin_patch(uid: str, b: UserPatch, a: User = Depends(need("admin", "super_admin")), db: Session = Depends(get_db)):
    t = db.get(User, uid)
    if not t: raise HTTPException(404, "User not found")
    ch = b.model_dump(exclude_unset=True)
    if ("role" in ch or t.role == "super_admin") and a.role != "super_admin": raise HTTPException(403, "Only super_admin can change roles")
    if t.id == a.id and ch.get("is_active") is False: raise HTTPException(400, "Cannot disable yourself")
    for k, v in ch.items(): setattr(t, k, v)
    audit(db, a, "admin.user.patch", t.id, ch); db.commit(); return {"ok": True}
@app.get("/api/admin/audit-logs")
def admin_audit(a: User = Depends(need("admin", "super_admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    return [{"actor": r.actor_id, "action": r.action, "target": r.target, "detail": r.detail, "at": str(r.created_at)} for r in rows]

def _timed(name, fn, *a):
    st = STATS[name]; t = time.perf_counter()
    try: return fn(*a)
    except Exception: st["errors"] += 1; raise
    finally:
        st["processed"] += 1; st["total_ms"] += (time.perf_counter() - t) * 1000
        st["last_run"] = dt.datetime.now(dt.timezone.utc).isoformat()
def pipeline(db, u, s, text, url):
    cid = str(uuid.uuid4())
    fp = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()
    if db.scalar(select(Listing).where(Listing.user_id == u.id, Listing.fingerprint == fp)):
        raise HTTPException(409, "Duplicate listing")
    ex = _timed("nlp_extraction", extract, text)
    rk = _timed("filter_antispam", risks, ex, s)
    sc = _timed("matching", score, ex, s, text)
    l = Listing(user_id=u.id, search_id=s.id, raw_text=text, source_url=url, fingerprint=fp, extracted=ex,
                score=sc["score"], score_detail=sc, risks=rk, status="new" if sc["score"] >= s.min_score else "rejected")
    db.add(l); db.commit()
    hub.publish(u.id, "listing.discovered" if l.status == "new" else "listing.rejected", {"id": l.id, "score": l.score}, cid)
    return l
@app.websocket("/ws")
async def ws(sock: WebSocket, token: str = ""):
    try: uid = read_token(token)
    except Exception: await sock.close(code=4401); return
    await sock.accept()
    q = asyncio.Queue(); hub.add(uid, q, asyncio.get_running_loop())
    try:
        while True:
            try: ev = await asyncio.wait_for(q.get(), 25)
            except asyncio.TimeoutError: ev = {"type": "heartbeat"}
            await sock.send_json(ev)
    except (WebSocketDisconnect, RuntimeError): pass
    finally: hub.remove(uid, q)
@app.get("/api/agents")
def agents(u: User = Depends(current_user)):
    return [{"name": n, "status": "ACTIVE" if v["processed"] else "IDLE", "processed": v["processed"], "errors": v["errors"],
             "last_run": v["last_run"], "avg_ms": round(v["total_ms"] / v["processed"], 2) if v["processed"] else None} for n, v in STATS.items()]
@app.get("/api/dashboard/overview")
def overview(u: User = Depends(current_user), db: Session = Depends(get_db)):
    L = db.scalars(select(Listing).where(Listing.user_id == u.id)).all()
    return {"total_listings": len(L), "high_quality": sum(l.score >= 80 for l in L), "filtered_out": sum(l.status == "rejected" for l in L),
            "active_searches": len(db.scalars(select(SearchConfig).where(SearchConfig.user_id == u.id, SearchConfig.active, SearchConfig.deleted_at.is_(None))).all()),
            "telegram_sources": len(db.scalars(select(TelegramSource).where(TelegramSource.user_id == u.id)).all())}
class TgIn(BaseModel): search_id: str
@app.post("/api/integrations/telegram/sources", status_code=201)
def tg_add(b: TgIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_search(db, u, b.search_id)
    t = TelegramSource(user_id=u.id, search_id=b.search_id, code=secrets.token_hex(6)); db.add(t); db.commit()
    return {"id": t.id, "link_command": f"/link {t.code}", "note": "Add your bot to the chat/channel, then send this command there to prove you control it."}
@app.get("/api/integrations/telegram/sources")
def tg_list(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": t.id, "search_id": t.search_id, "linked": t.chat_id is not None} for t in db.scalars(select(TelegramSource).where(TelegramSource.user_id == u.id))]
@app.delete("/api/integrations/telegram/sources/{tid}", status_code=204)
def tg_del(tid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(TelegramSource, tid)
    if not t or t.user_id != u.id: raise HTTPException(404, "Source not found")
    db.delete(t); db.commit()
@app.post("/api/integrations/telegram/webhook")
async def tg_webhook(req: Request, x_telegram_bot_api_secret_token: str = Header(""), db: Session = Depends(get_db)):
    sec = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if not sec: raise HTTPException(503, "Telegram not configured")
    if not hmac.compare_digest(x_telegram_bot_api_secret_token, sec): raise HTTPException(403, "Bad secret")
    m = (await req.json()).get("message") or (await req.json()).get("channel_post") or {}
    text = m.get("text") or m.get("caption") or ""; chat = str((m.get("chat") or {}).get("id", ""))
    if not text or chat == "": return {"processed": 0}
    if text.startswith("/link "):
        src = db.scalar(select(TelegramSource).where(TelegramSource.code == text[6:].strip()))
        if src and not src.chat_id: src.chat_id = chat; db.commit(); return {"linked": True}
        return {"linked": False}
    n = 0
    for src in db.scalars(select(TelegramSource).where(TelegramSource.chat_id == chat)):
        s, u = db.get(SearchConfig, src.search_id), db.get(User, src.user_id)
        if s and not s.deleted_at and s.active and u and u.is_active:
            try: pipeline(db, u, s, text, None); n += 1
            except HTTPException: pass
    return {"processed": n}
