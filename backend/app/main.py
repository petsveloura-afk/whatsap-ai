import asyncio, json, logging, hashlib, hmac, os, secrets, time, uuid, datetime as dt
from fastapi import FastAPI, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base, engine, get_db
from .models import UserPreference, AiMemory, User, SearchConfig, Listing, AuditLog, TelegramSource, RefreshToken, PasswordReset, Subscription, PaymentEvent
from . import mail, paypal, whatsapp
from fastapi.middleware.cors import CORSMiddleware
from .events import hub, STATS
from .security import hash_pw, check_pw, make_token, read_token
from .extract import extract
from .scoring import score, risks
from .nlsearch import parse_search
from .neardup import is_near_duplicate, embed
from .memory import adjustment, MAX_MEMORIES
from .ratelimit import limiter
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
def login(c: Cred, request: Request, db: Session = Depends(get_db)):
    if not limiter.allow("login:" + (request.client.host if request.client else "?") + ":" + c.email.lower(), 10, 300): raise HTTPException(429, "Too many attempts; try again later")
    u = db.scalar(select(User).where(User.email == c.email.lower()))
    if not u or not check_pw(c.password, u.password_hash): raise HTTPException(401, "Invalid credentials")
    return _issue(db, u.id)
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
    n = len(db.scalars(select(SearchConfig).where(SearchConfig.user_id == u.id, SearchConfig.deleted_at.is_(None))).all())
    if n >= PLANS[_plan(db, u)]["max_searches"]: raise HTTPException(402, "Search limit reached for your plan")
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
class NlIn(BaseModel): text: str = Field(min_length=5, max_length=1000)
@app.post("/api/searches/parse")
def parse_nl(b: NlIn, u: User = Depends(current_user)):
    """Free rule-based natural-language -> search parameters (no external AI cost)."""
    return parse_search(b.text)
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

def _personalization_on(db, u):
    p = db.scalar(select(UserPreference).where(UserPreference.user_id == u.id)); return p.personalization_enabled if p else True
def _remember(db, u, kind, text):
    if not _personalization_on(db, u): return
    db.add(AiMemory(user_id=u.id, kind=kind, text=text[:2000], embedding=embed(text)))
    old = db.scalars(select(AiMemory).where(AiMemory.user_id == u.id).order_by(AiMemory.created_at.desc()).offset(MAX_MEMORIES)).all()
    for o in old: db.delete(o)
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
        l = _own_listing(db, u, lid); l.status = status
        if status in ("saved", "rejected"): _remember(db, u, status, l.raw_text)
        db.commit(); return {"id": l.id, "status": status}
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
            "listings": [cols(x) for x in db.scalars(select(Listing).where(Listing.user_id == u.id))],
            "memory": [{"id": m.id, "kind": m.kind, "text": m.text, "at": str(m.created_at)} for m in db.scalars(select(AiMemory).where(AiMemory.user_id == u.id))],
            "personalization_enabled": _personalization_on(db, u)}
@app.delete("/api/me", status_code=204)
def delete_me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for M in (AiMemory, UserPreference, Listing, SearchConfig):
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
    recent = [x.raw_text for x in db.scalars(select(Listing).where(Listing.user_id == u.id, Listing.search_id == s.id).order_by(Listing.created_at.desc()).limit(200))]
    if is_near_duplicate(text, recent): raise HTTPException(409, "Near-duplicate listing")
    ex = _timed("nlp_extraction", extract, text)
    pers = None
    rk = _timed("filter_antispam", risks, ex, s)
    sc = _timed("matching", score, ex, s, text)
    if _personalization_on(db, u) and not sc["rejection_reasons"]:
        mem = db.scalars(select(AiMemory).where(AiMemory.user_id == u.id)).all()
        pers = adjustment(text, [m.embedding for m in mem if m.kind == "saved"], [m.embedding for m in mem if m.kind == "rejected"])
        sc["score"] = max(0, min(100, sc["score"] + pers["points"])); sc["personalization"] = pers
    l = Listing(user_id=u.id, search_id=s.id, raw_text=text, source_url=url, fingerprint=fp, extracted=ex,
                score=sc["score"], score_detail=sc, risks=rk, status="new" if sc["score"] >= s.min_score else "rejected")
    db.add(l); db.commit()
    hub.publish(u.id, "listing.discovered" if l.status == "new" else "listing.rejected", {"id": l.id, "score": l.score}, cid)
    if l.status == "new" and u.whatsapp_consent and u.whatsapp_number and whatsapp.configured():
        try: whatsapp.notify(u.whatsapp_number, f"Smart Sniper: new match {l.score}% - {ex.get('location') or ''} {ex.get('price') or ''}")
        except Exception as e: log.warning("whatsapp failed: %s", type(e).__name__)
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

log = logging.getLogger("sniper"); logging.basicConfig(level=logging.INFO, format="%(message)s")
METRICS = {"requests": 0, "by_status": {}, "total_ms": 0.0}
app.add_middleware(CORSMiddleware, allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o], allow_methods=["*"], allow_headers=["*"])
@app.middleware("http")
async def obs(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4()); t = time.perf_counter()
    resp = await call_next(request); ms = (time.perf_counter() - t) * 1000
    METRICS["requests"] += 1; k = str(resp.status_code); METRICS["by_status"][k] = METRICS["by_status"].get(k, 0) + 1; METRICS["total_ms"] += ms
    resp.headers["X-Request-ID"] = rid
    log.info(json.dumps({"rid": rid, "method": request.method, "path": request.url.path, "status": resp.status_code, "ms": round(ms, 1)}))
    return resp
@app.get("/api/admin/metrics")
def metrics(a: User = Depends(need("admin", "super_admin"))):
    return {**METRICS, "avg_ms": round(METRICS["total_ms"] / METRICS["requests"], 2) if METRICS["requests"] else None, "agents": STATS}
def _h(x): return hashlib.sha256(x.encode()).hexdigest()
def _now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
def _issue(db, uid):
    raw = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=uid, token_hash=_h(raw), expires_at=_now() + dt.timedelta(days=14))); db.commit()
    return {"access_token": make_token(uid), "refresh_token": raw, "token_type": "bearer"}
def _revoke_all(db, uid):
    for x in db.scalars(select(RefreshToken).where(RefreshToken.user_id == uid)): x.revoked = True
class RefreshIn(BaseModel): refresh_token: str
@app.post("/api/auth/refresh")
def refresh(b: RefreshIn, db: Session = Depends(get_db)):
    t = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _h(b.refresh_token)))
    if not t: raise HTTPException(401, "Invalid refresh token")
    if t.revoked: _revoke_all(db, t.user_id); db.commit(); raise HTTPException(401, "Token reuse detected; sessions revoked")
    u = db.get(User, t.user_id)
    if t.expires_at.replace(tzinfo=None) < _now() or not u or not u.is_active: raise HTTPException(401, "Expired")
    t.revoked = True; return _issue(db, u.id)
@app.post("/api/auth/logout", status_code=204)
def logout(b: RefreshIn, db: Session = Depends(get_db)):
    t = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _h(b.refresh_token)))
    if t: t.revoked = True; db.commit()
class EmailIn(BaseModel): email: EmailStr
@app.post("/api/auth/forgot-password", status_code=202)
def forgot(b: EmailIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == b.email.lower()))
    if u:
        raw = secrets.token_urlsafe(32)
        db.add(PasswordReset(user_id=u.id, token_hash=_h(raw), expires_at=_now() + dt.timedelta(hours=1))); db.commit()
        try: mail.send_mail(u.email, "Reset your Smart Sniper password", f"{os.environ.get('APP_URL', '')}/reset?token={raw}")
        except Exception as e: log.warning("reset mail failed: %s", type(e).__name__)
    return {"status": "If the account exists, an email was sent"}
class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=10)
@app.post("/api/auth/reset-password")
def reset(b: ResetIn, db: Session = Depends(get_db)):
    r = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == _h(b.token)))
    if not r or r.used or r.expires_at.replace(tzinfo=None) < _now(): raise HTTPException(400, "Invalid or expired token")
    u = db.get(User, r.user_id); u.password_hash = hash_pw(b.password); r.used = True; _revoke_all(db, u.id); db.commit()
    return {"ok": True}
PLANS = {"starter": {"price": 0, "max_searches": 3}, "pro": {"price": 99, "max_searches": 15}, "vip": {"price": 149, "max_searches": 50}}
def _sub(db, u): return db.scalar(select(Subscription).where(Subscription.user_id == u.id))
def _plan(db, u):
    s = _sub(db, u); return s.plan if s and s.status == "active" else "starter"
@app.get("/api/billing/plans")
def plans(): return [{"id": k, **v, "currency": "ILS", "available": k == "starter" or (paypal.configured() and bool(paypal.plan_ids()[k]))} for k, v in PLANS.items()]
@app.get("/api/billing/subscription")
def my_sub(u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _sub(db, u); return {"plan": _plan(db, u), "status": s.status if s else "none"}
class CheckoutIn(BaseModel): plan: str = Field(pattern="^(pro|vip)$")
@app.post("/api/billing/checkout")
def checkout(b: CheckoutIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    pid = paypal.plan_ids()[b.plan]
    if not paypal.configured() or not pid: raise HTTPException(503, "PayPal not configured")
    if _plan(db, u) != "starter": raise HTTPException(409, "Already subscribed")
    app_url = os.environ.get("APP_URL", "")
    sid, href = paypal.create_subscription(pid, u.id, app_url + "/?billing=return", app_url + "/?billing=cancel")
    s = _sub(db, u) or Subscription(user_id=u.id); s.plan, s.status, s.paypal_subscription_id = b.plan, "pending", sid; db.add(s); db.commit()
    return {"approve_url": href}  # activation happens ONLY via verified webhook
@app.post("/api/billing/cancel")
def cancel(u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _sub(db, u)
    if not s or s.status != "active": raise HTTPException(409, "No active subscription")
    paypal.cancel_subscription(s.paypal_subscription_id); return {"status": "cancellation requested; confirmed by webhook"}
@app.post("/api/webhooks/paypal")
async def pp_webhook(req: Request, db: Session = Depends(get_db)):
    ev = await req.json()
    if not paypal.verify_webhook({k.lower(): v for k, v in req.headers.items()}, ev): raise HTTPException(400, "Invalid signature")
    if not ev.get("id"): raise HTTPException(400, "Missing event id")
    if db.get(PaymentEvent, ev["id"]): return {"duplicate": True}
    db.add(PaymentEvent(id=ev["id"])); r, t = ev.get("resource", {}), ev.get("event_type", "")
    if t == "BILLING.SUBSCRIPTION.ACTIVATED" and r.get("custom_id") and db.get(User, r["custom_id"]):
        plan = next((k for k, v in paypal.plan_ids().items() if v and v == r.get("plan_id")), None)
        if plan:
            s = db.scalar(select(Subscription).where(Subscription.user_id == r["custom_id"])) or Subscription(user_id=r["custom_id"])
            s.plan, s.status, s.paypal_subscription_id = plan, "active", r.get("id"); db.add(s)
    elif t.startswith("BILLING.SUBSCRIPTION."):
        s = db.scalar(select(Subscription).where(Subscription.paypal_subscription_id == r.get("id")))
        new = {"CANCELLED": "canceled", "SUSPENDED": "canceled", "EXPIRED": "canceled", "PAYMENT.FAILED": "past_due"}.get(t.removeprefix("BILLING.SUBSCRIPTION."))
        if s and new: s.status = new
    db.commit(); return {"ok": True}
class WaIn(BaseModel):
    number: str = Field(pattern=r"^\+?\d{8,15}$")
    consent: bool
@app.put("/api/integrations/whatsapp/consent")
def wa_consent(b: WaIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.whatsapp_number, u.whatsapp_consent = b.number.lstrip("+"), b.consent; db.commit(); return {"consent": b.consent}
@app.get("/api/integrations/whatsapp/status")
def wa_status(u: User = Depends(current_user)):
    return {"provider": "whatsapp_cloud_api", "configured": whatsapp.configured(), "consent": bool(u.whatsapp_consent), "qr_pairing": "unsupported (unofficial; may violate WhatsApp terms)"}

@app.get("/api/memory")
def memory_list(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AiMemory).where(AiMemory.user_id == u.id).order_by(AiMemory.created_at.desc())).all()
    return {"personalization_enabled": _personalization_on(db, u), "items": [{"id": m.id, "kind": m.kind, "text": m.text[:200], "at": str(m.created_at)} for m in rows]}
class PrefIn(BaseModel): personalization_enabled: bool
@app.put("/api/memory/preferences")
def memory_pref(b: PrefIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.scalar(select(UserPreference).where(UserPreference.user_id == u.id)) or UserPreference(user_id=u.id)
    p.personalization_enabled = b.personalization_enabled; db.add(p); db.commit(); return {"personalization_enabled": p.personalization_enabled}
@app.delete("/api/memory", status_code=204)
def memory_clear(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for m in db.scalars(select(AiMemory).where(AiMemory.user_id == u.id)): db.delete(m)
    db.commit()
@app.delete("/api/memory/{mid}", status_code=204)
def memory_del(mid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(AiMemory, mid)
    if not m or m.user_id != u.id: raise HTTPException(404, "Memory item not found")
    db.delete(m); db.commit()
