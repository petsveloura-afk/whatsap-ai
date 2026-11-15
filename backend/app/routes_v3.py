"""v3.1: sellable free features (API keys + public API, signed webhooks, referrals, share links, market brain, weekly digest),
self-hosted error tracking, security headers, shared rate limiting, multi-instance queue safety, optional RLS.
Imported at the bottom of main.py. Existing routes/modules are unchanged; this file only adds."""
import datetime as dt, hashlib, logging, os, time, uuid
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from .db import get_db, SessionLocal, Base, engine
from .models import User, Listing, SearchConfig
from .models2 import DataSource, SystemSetting, AdminAction, AgentJob
from .models3 import (ApiKey, WebhookEndpoint, WebhookDelivery, Referral, SharedLink, UserFlag, MarketObservation, RateHit, ErrorEvent)
from . import growth, market, scout, jobqueue, errtrack, rls, scale, mail, adapters_extra  # adapters_extra registers new Scout kinds
from . import main as _m
from . import routes_v2
from .ratelimit_db import SharedLimiter, prune
from .security import read_token

router = APIRouter(); log = logging.getLogger("sniper")
ADMIN = routes_v2.ADMIN; STAFF = routes_v2.STAFF
def _now(): return dt.datetime.now(dt.timezone.utc)
def _naive(t): return t.replace(tzinfo=None) if t else t
def _flag(db, uid, name) -> bool:
    r = db.scalar(select(UserFlag).where(UserFlag.user_id == uid, UserFlag.name == name)); return bool(r and r.value)
def _set_flag(db, uid, name, val: bool):
    r = db.scalar(select(UserFlag).where(UserFlag.user_id == uid, UserFlag.name == name))
    if r: r.value = val
    else: db.add(UserFlag(user_id=uid, name=name, value=val))
    db.commit()
def _own_listing(db, u, lid):
    l = db.get(Listing, lid)
    if not l or l.user_id != u.id: raise HTTPException(404, "Listing not found")
    return l

# ================= API keys + public API =================
class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    scopes: list[str] = Field(default_factory=lambda: ["read"])
MAX_KEYS = 5
@router.post("/api/keys", status_code=201)
def key_create(b: KeyIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    if any(s not in growth.SCOPES for s in b.scopes): raise HTTPException(422, "scopes must be from: " + ", ".join(growth.SCOPES))
    if db.scalar(select(func.count()).select_from(ApiKey).where(ApiKey.user_id == u.id, ApiKey.active)) >= MAX_KEYS: raise HTTPException(409, f"At most {MAX_KEYS} active keys")
    raw, prefix, h = growth.new_api_key(); k = ApiKey(user_id=u.id, name=b.name, prefix=prefix, key_hash=h, scopes=sorted(set(b.scopes))); db.add(k); db.commit()
    _m.audit(db, u, "apikey.created", k.id); db.commit()
    return {"id": k.id, "key": raw, "prefix": prefix, "scopes": k.scopes, "note": "Store this key now - it is shown only once."}
@router.get("/api/keys")
def key_list(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    return [{"id": k.id, "name": k.name, "prefix": k.prefix, "scopes": k.scopes, "active": k.active, "last_used_at": str(k.last_used_at) if k.last_used_at else None}
            for k in db.scalars(select(ApiKey).where(ApiKey.user_id == u.id).order_by(ApiKey.created_at.desc()))]
@router.delete("/api/keys/{kid}", status_code=204)
def key_revoke(kid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    k = db.get(ApiKey, kid)
    if not k or k.user_id != u.id: raise HTTPException(404, "Key not found")
    k.active = False; _m.audit(db, u, "apikey.revoked", k.id); db.commit()

def _referrals(db, uid) -> int:
    return db.scalar(select(func.count()).select_from(Referral).where(Referral.user_id == uid, Referral.referred_user_id.is_not(None))) or 0
def api_auth(scope: str):
    def dep(x_api_key: str = Header(""), db: Session = Depends(get_db)) -> User:
        k = db.scalar(select(ApiKey).where(ApiKey.key_hash == growth.hash_key(x_api_key), ApiKey.active)) if x_api_key.startswith(growth.KEY_PREFIX) else None
        u = db.get(User, k.user_id) if k else None
        if not k or not u or not u.is_active: raise HTTPException(401, "Invalid API key")
        if scope not in k.scopes: raise HTTPException(403, f"Key lacks '{scope}' scope")
        quota = growth.daily_quota(_m._plan(db, u), _referrals(db, u.id))
        if not _m.limiter.allow("api:" + u.id, quota, 86400): raise HTTPException(429, f"Daily quota of {quota} requests reached")
        k.last_used_at = _now(); db.commit(); return u
    return dep
def _row(l): return {"id": l.id, "search_id": l.search_id, "score": l.score, "status": l.status, "extracted": l.extracted, "risks": l.risks, "source_url": l.source_url, "created_at": str(l.created_at)}
@router.get("/api/public/v1/listings")
def pub_listings(limit: int = 50, min_score: int = 0, u: User = Depends(api_auth("read")), db: Session = Depends(get_db)):
    q = select(Listing).where(Listing.user_id == u.id, Listing.score >= min_score).order_by(Listing.created_at.desc()).limit(max(1, min(limit, 200)))
    return {"items": [_row(l) for l in db.scalars(q)]}
class PubIngest(BaseModel):
    search_id: str; text: str = Field(min_length=5, max_length=5000); url: str | None = Field(None, max_length=1000)
@router.post("/api/public/v1/ingest", status_code=201)
def pub_ingest(b: PubIngest, u: User = Depends(api_auth("ingest")), db: Session = Depends(get_db)):
    s = _m._own_search(db, u, b.search_id); return _row(_m.pipeline(db, u, s, b.text, b.url))
@router.get("/api/public/v1/usage")
def pub_usage(u: User = Depends(api_auth("read")), db: Session = Depends(get_db)):
    plan = _m._plan(db, u); return {"plan": plan, "daily_quota": growth.daily_quota(plan, _referrals(db, u.id)), "referrals": _referrals(db, u.id)}

# ================= signed webhooks (outbound) =================
class HookIn(BaseModel):
    url: str = Field(max_length=1000); min_score: int = Field(60, ge=0, le=100)
MAX_HOOKS = 5
@router.post("/api/hooks", status_code=201)
def hook_add(b: HookIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    try: scout.check_url(b.url)
    except scout.UnsafeURL as e: raise HTTPException(422, str(e))
    if not b.url.startswith("https://"): raise HTTPException(422, "Webhook URL must be https")
    if db.scalar(select(func.count()).select_from(WebhookEndpoint).where(WebhookEndpoint.user_id == u.id)) >= MAX_HOOKS: raise HTTPException(409, f"At most {MAX_HOOKS} webhooks")
    h = WebhookEndpoint(user_id=u.id, url=b.url.strip(), secret=growth.new_secret(), min_score=b.min_score, cursor_at=_now()); db.add(h); db.commit()
    return {"id": h.id, "url": h.url, "secret": h.secret, "min_score": h.min_score, "note": "Verify the X-Sniper-Signature header (t=<unix>,v1=<hmac-sha256 of '<t>.<body>'>) with this secret."}
@router.get("/api/hooks")
def hook_list(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    return [{"id": h.id, "url": h.url, "min_score": h.min_score, "active": h.active, "fail_count": h.fail_count} for h in db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.user_id == u.id))]
def _own_hook(db, u, hid):
    h = db.get(WebhookEndpoint, hid)
    if not h or h.user_id != u.id: raise HTTPException(404, "Webhook not found")
    return h
@router.delete("/api/hooks/{hid}", status_code=204)
def hook_del(hid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    db.delete(_own_hook(db, u, hid)); db.commit()
@router.post("/api/hooks/{hid}/test", status_code=202)
def hook_test(hid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    h = _own_hook(db, u, hid); jobqueue.enqueue(db, "webhook_deliver", {"endpoint_id": h.id, "listing_id": None}, user_id=u.id); return {"queued": True}
@router.get("/api/hooks/{hid}/deliveries")
def hook_deliveries(hid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _own_hook(db, u, hid)
    return [{"status": d.status, "http_status": d.http_status, "detail": d.detail, "at": str(d.created_at)} for d in db.scalars(select(WebhookDelivery).where(WebhookDelivery.endpoint_id == hid).order_by(WebhookDelivery.created_at.desc()).limit(50))]

def handle_webhook(db: Session, job: AgentJob, client=None):
    """Raises on failure so the queue retries with backoff; endpoint auto-disables after repeated failures."""
    h = db.get(WebhookEndpoint, job.payload.get("endpoint_id"))
    if not h or not h.active: return
    l = db.get(Listing, job.payload["listing_id"]) if job.payload.get("listing_id") else None
    body = growth.webhook_body("listing.new" if l else "ping", _row(l) if l else {"message": "test delivery"})
    sig, _ = growth.sign(h.secret, body); own = client is None; client = client or httpx.Client()
    try:
        scout.check_url(h.url)
        r = client.post(h.url, content=body, headers={"Content-Type": "application/json", "X-Sniper-Signature": sig, "User-Agent": scout.UA}, timeout=10, follow_redirects=False)
        ok = 200 <= r.status_code < 300
        db.add(WebhookDelivery(user_id=h.user_id, endpoint_id=h.id, listing_id=l.id if l else None, status="ok" if ok else "failed", http_status=r.status_code, detail=None if ok else "non-2xx"))
        h.fail_count = 0 if ok else h.fail_count + 1; db.commit()
        if not ok: raise RuntimeError(f"webhook returned {r.status_code}")
    except RuntimeError: raise
    except Exception as e:
        db.rollback(); h = db.get(WebhookEndpoint, h.id); h.fail_count += 1
        if h.fail_count >= 15: h.active = False
        db.add(WebhookDelivery(user_id=h.user_id, endpoint_id=h.id, listing_id=l.id if l else None, status="failed", detail=f"{type(e).__name__}: {str(e)[:200]}")); db.commit(); raise
    finally:
        if own: client.close()

def webhook_fanout(db: Session) -> int:
    n = 0
    for h in db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.active)):
        since = h.cursor_at or h.created_at
        rows = db.scalars(select(Listing).where(Listing.user_id == h.user_id, Listing.status == "new", Listing.score >= h.min_score, Listing.created_at > since).order_by(Listing.created_at).limit(50)).all()
        for l in rows: n += jobqueue.enqueue(db, "webhook_deliver", {"endpoint_id": h.id, "listing_id": l.id}, user_id=h.user_id, dedupe_key=f"wh:{h.id}:{l.id}") is not None
        if rows: h.cursor_at = rows[-1].created_at; db.commit()
    return n

# ================= referrals =================
@router.get("/api/referrals/me")
def ref_me(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(Referral).where(Referral.user_id == u.id, Referral.referred_user_id.is_(None)))
    if not r:
        r = Referral(user_id=u.id, code=growth.new_code()); db.add(r); db.commit()
    n = _referrals(db, u.id)
    return {"code": r.code, "referred": n, "bonus_daily_api_requests": growth.REFERRAL_BONUS_REQUESTS * min(n, growth.REFERRAL_BONUS_CAP)}
class ClaimIn(BaseModel): code: str = Field(min_length=8, max_length=8)
@router.post("/api/referrals/claim")
def ref_claim(b: ClaimIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    if db.scalar(select(Referral).where(Referral.referred_user_id == u.id)): raise HTTPException(409, "You already used a referral code")
    owner = db.scalar(select(Referral).where(Referral.code == b.code.upper(), Referral.referred_user_id.is_(None)))
    if not owner or owner.user_id == u.id: raise HTTPException(404, "Invalid referral code")
    db.add(Referral(user_id=owner.user_id, code=None, referred_user_id=u.id)); db.commit(); return {"ok": True}

# ================= shareable deal links =================
@router.post("/api/listings/{lid}/share", status_code=201)
def share_create(lid: str, days: int = 7, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own_listing(db, u, lid); tok, h = growth.new_share_token()
    s = SharedLink(user_id=u.id, listing_id=l.id, token_hash=h, expires_at=_now() + dt.timedelta(days=max(1, min(days, 30)))); db.add(s); db.commit()
    return {"id": s.id, "token": tok, "path": f"/api/public/shared/{tok}", "expires_at": str(s.expires_at)}
@router.get("/api/public/shared/{token}")
def share_view(token: str, db: Session = Depends(get_db)):
    s = db.scalar(select(SharedLink).where(SharedLink.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    if not s or s.revoked or _naive(s.expires_at) < _naive(_now()): raise HTTPException(404, "Link not found or expired")
    l = db.get(Listing, s.listing_id)
    if not l: raise HTTPException(404, "Link not found or expired")
    return growth.public_listing(l)
@router.delete("/api/shares/{sid}", status_code=204)
def share_revoke(sid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    s = db.get(SharedLink, sid)
    if not s or s.user_id != u.id: raise HTTPException(404, "Link not found")
    s.revoked = True; db.commit()

# ================= market brain =================
def _comps(db, u, ex: dict, exclude_id: str | None = None) -> list[float]:
    own = [{**{k: x.extracted.get(k) for k in ("category", "location", "rooms", "price")}} for x in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(500)) if x.id != exclude_id]
    pool = []
    if ex.get("category"):
        q = select(MarketObservation).where(MarketObservation.category == ex["category"]).order_by(MarketObservation.observed_at.desc()).limit(2000)
        pool = [{"category": o.category, "location": o.location, "rooms": o.rooms, "price": o.price} for o in db.scalars(q)]
    return market.comparable(ex, own + pool)
@router.get("/api/listings/{lid}/insight")
def insight(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own_listing(db, u, lid); ex = l.extracted or {}
    return {"listing_id": l.id, **market.deal_insight(ex.get("price"), _comps(db, u, ex, l.id))}
@router.get("/api/market/stats")
def mstats(category: str, location: str | None = None, rooms: float | None = None, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    return market.summarize(_comps(db, u, {"category": category, "location": location, "rooms": rooms}))
@router.get("/api/market/trend")
def mtrend(category: str, location: str | None = None, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    pts = [(_naive(x.created_at), x.extracted["price"]) for x in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(1000))
           if x.extracted.get("category") == category and x.extracted.get("price") and (not location or x.extracted.get("location") == location)]
    return market.weekly_trend(pts)
class PoolIn(BaseModel): enabled: bool
@router.put("/api/market/pool")
def mpool(b: PoolIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    """Opt-in: share anonymised price points (category, area, rooms, price - no text, no identity) to improve everyone's comparisons."""
    _set_flag(db, u.id, "market_pool", b.enabled); return {"enabled": b.enabled}
@router.get("/api/market/pool")
def mpool_get(u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return {"enabled": _flag(db, u.id, "market_pool")}

def market_sync(db: Session) -> int:
    row = db.get(SystemSetting, "market_cursor"); cur = dt.datetime.fromisoformat(row.value["at"]) if row else _now() - dt.timedelta(days=1)
    users = [f.user_id for f in db.scalars(select(UserFlag).where(UserFlag.name == "market_pool", UserFlag.value))]
    if not users: return 0
    rows = db.scalars(select(Listing).where(Listing.user_id.in_(users), Listing.created_at > cur).order_by(Listing.created_at).limit(500)).all(); n = 0
    for l in rows:
        ex = l.extracted or {}
        if ex.get("price") and ex.get("category"): db.add(MarketObservation(category=ex["category"], location=ex.get("location"), rooms=ex.get("rooms"), price=ex["price"])); n += 1
    if rows:
        last = rows[-1].created_at; last = last if last.tzinfo else last.replace(tzinfo=dt.timezone.utc)
        if row: row.value = {"at": last.isoformat()}
        else: db.add(SystemSetting(key="market_cursor", value={"at": last.isoformat()}))
    db.commit(); return n

# ================= weekly digest =================
@router.put("/api/digest/subscribe")
def digest_sub(b: PoolIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _set_flag(db, u.id, "weekly_digest", b.enabled); return {"enabled": b.enabled, "email_configured": bool(os.environ.get("SMTP_HOST"))}
def _digest_rows(db, u, days=7):
    since = _now() - dt.timedelta(days=days)
    return [{"score": l.score, "location": (l.extracted or {}).get("location"), "price": (l.extracted or {}).get("price"), "verdict": market.deal_insight((l.extracted or {}).get("price"), _comps(db, u, l.extracted or {}, l.id))["verdict"]}
            for l in db.scalars(select(Listing).where(Listing.user_id == u.id, Listing.status == "new", Listing.created_at > since))]
@router.get("/api/digest/preview")
def digest_preview(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    s, b = growth.build_digest(u.email, _digest_rows(db, u)); return {"subject": s, "body": b}
def handle_digest(db: Session, job: AgentJob):
    u = db.get(User, job.payload.get("user_id"))
    if not u or not u.is_active or not _flag(db, u.id, "weekly_digest") or not os.environ.get("SMTP_HOST"): return
    s, b = growth.build_digest(u.email, _digest_rows(db, u)); mail.send_mail(u.email, s, b)
def digest_schedule(db: Session) -> int:
    n = 0
    for f in db.scalars(select(UserFlag).where(UserFlag.name == "weekly_digest", UserFlag.value)):
        row = db.get(SystemSetting, "digest_last:" + f.user_id)
        if row and _now() - dt.datetime.fromisoformat(row.value["at"]) < dt.timedelta(days=6, hours=12): continue
        if jobqueue.enqueue(db, "digest_send", {"user_id": f.user_id}, user_id=f.user_id, dedupe_key="digest:" + f.user_id):
            v = {"at": _now().isoformat()}
            if row: row.value = v
            else: db.add(SystemSetting(key="digest_last:" + f.user_id, value=v))
            db.commit(); n += 1
    return n

# ================= extra exports / purge =================
def purge_user_data(db: Session, uid: str):
    """Delete every row owned by the user across ALL tables with a user_id column (FK-safe order). Used by DELETE /api/me."""
    for t in reversed(Base.metadata.sorted_tables):
        if t.name == "users": continue
        if "user_id" in t.c: db.execute(t.delete().where(t.c.user_id == uid))
        else:  # child tables without their own user_id (listing_scores, listing_images, integration_sessions ...): remove via their parent
            for fk in t.foreign_keys:
                parent = fk.column.table
                if parent.name != "users" and "user_id" in parent.c:
                    db.execute(t.delete().where(fk.parent.in_(select(fk.column).where(parent.c.user_id == uid))))
        if t.name == "referrals": db.execute(t.delete().where(t.c.referred_user_id == uid))
    db.flush()
@router.get("/api/me/export/full")
def export_full(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    skip = {"password_hash", "key_hash", "secret", "token_hash", "embedding"}
    out = {}
    for t in Base.metadata.sorted_tables:
        if t.name in ("users", "refresh_tokens", "password_resets") or "user_id" not in t.c: continue
        rows = db.execute(select(t).where(t.c.user_id == u.id)).mappings().all()
        out[t.name] = [{k: (str(v) if isinstance(v, (dt.datetime, dt.date)) else v) for k, v in r.items() if k not in skip} for r in rows]
    return {"user": {"id": u.id, "email": u.email, "role": u.role}, "tables": out}

# ================= admin: errors + growth =================
@router.get("/api/admin/errors")
def admin_errors(resolved: bool = False, a: User = Depends(_m.need(*STAFF)), db: Session = Depends(get_db)):
    return [{"id": e.id, "kind": e.kind, "message": e.message, "route": e.route, "count": e.count, "resolved": e.resolved, "first_seen": str(e.first_seen), "last_seen": str(e.last_seen), "sample": e.sample}
            for e in db.scalars(select(ErrorEvent).where(ErrorEvent.resolved == resolved).order_by(ErrorEvent.last_seen.desc()).limit(100))]
@router.post("/api/admin/errors/{eid}/resolve")
def admin_err_resolve(eid: str, a: User = Depends(_m.need(*ADMIN)), db: Session = Depends(get_db)):
    e = db.get(ErrorEvent, eid)
    if not e: raise HTTPException(404, "Not found")
    e.resolved = True; db.add(AdminAction(admin_id=a.id, action="error.resolve", target=eid)); db.commit(); return {"ok": True}
@router.get("/api/admin/growth")
def admin_growth(a: User = Depends(_m.need(*STAFF)), db: Session = Depends(get_db)):
    c = lambda M, *w: db.scalar(select(func.count()).select_from(M).where(*w)) or 0
    return {"api_keys_active": c(ApiKey, ApiKey.active), "webhooks_active": c(WebhookEndpoint, WebhookEndpoint.active), "referrals": c(Referral, Referral.referred_user_id.is_not(None)),
            "market_pool_users": c(UserFlag, UserFlag.name == "market_pool", UserFlag.value), "market_observations": c(MarketObservation), "digest_subscribers": c(UserFlag, UserFlag.name == "weekly_digest", UserFlag.value),
            "open_errors": c(ErrorEvent, ErrorEvent.resolved == False), "queue": jobqueue.stats(db)}  # noqa: E712

# ================= edge middleware: error capture, request id, security headers, RLS context =================
_RLS_BYPASS = ("/api/admin", "/api/auth", "/api/webhooks", "/api/public", "/api/health")
async def edge(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    if rls.ENFORCE():
        uid = None
        if not request.url.path.startswith(_RLS_BYPASS):
            try: uid = read_token(request.headers.get("authorization", "").removeprefix("Bearer "))
            except Exception: uid = None
        rls.current_uid.set(uid)
    try: resp = await call_next(request)
    except Exception as e:
        try:
            with SessionLocal() as db: errtrack.capture(db, e, f"{request.method} {request.url.path}")
        except Exception: pass
        log.error("unhandled error rid=%s %s %s", rid, request.method, request.url.path)
        resp = JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500)
    resp.headers.update({"X-Request-ID": rid, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                         "Permissions-Policy": "geolocation=(), camera=(), microphone=()", "Cross-Origin-Opener-Policy": "same-origin"})
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https": resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp

# ================= wiring (called once from main.py) =================
def housekeeping(db: Session) -> dict:
    return {"recovered": scale.recover_stale(db), "rate_hits_pruned": prune(db, 90000)}
def tick(db: Session) -> dict:
    """One scheduler pass (idempotent; safe if several instances run it). Each step is isolated so one failure doesn't block the rest."""
    out = {}
    for name, fn in (("webhooks", webhook_fanout), ("digest", digest_schedule), ("market", market_sync), ("housekeeping", housekeeping)):
        try: out[name] = fn(db)
        except Exception as e:
            db.rollback(); out[name] = f"error:{type(e).__name__}"; log.warning("tick %s failed: %s", name, type(e).__name__); errtrack.capture(db, e, "tick:" + name)
    db.commit(); return out
_installed = False
def install():
    global _installed
    if _installed: return
    _installed = True
    if os.environ.get("AUTO_CREATE_TABLES") == "1": Base.metadata.create_all(engine)  # dev/tests only; includes v3.1 tables
    routes_v2.HANDLERS.update({"webhook_deliver": handle_webhook, "digest_send": handle_digest})
    if engine.dialect.name == "postgresql":
        _m.limiter = SharedLimiter(); jobqueue.claim = scale.claim   # multi-instance safe on Postgres; SQLite keeps the in-memory defaults
    rls.install(SessionLocal)
    orig = routes_v2.schedule_due
    def schedule_with_growth(db):
        n = orig(db); tick(db); return n
    routes_v2.schedule_due = schedule_with_growth
