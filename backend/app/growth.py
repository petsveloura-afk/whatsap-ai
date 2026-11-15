"""Sellable free features: API keys, signed webhooks, referrals, shareable deal links, weekly digest. Pure helpers here;
HTTP wiring is in routes_v3.py. Nothing here calls a paid service."""
import hashlib, hmac, json, secrets, time, datetime as dt

# ---- API keys: shown once, stored as sha256 ----
KEY_PREFIX = "ssk_"
SCOPES = ("read", "ingest")
PLAN_DAILY_QUOTA = {"starter": 200, "pro": 5000, "vip": 50000}
REFERRAL_BONUS_REQUESTS = 100   # extra daily API requests per successful referral (cap below)
REFERRAL_BONUS_CAP = 20
def new_api_key() -> tuple[str, str, str]:
    raw = KEY_PREFIX + secrets.token_urlsafe(32); return raw, raw[:10], hash_key(raw)
def hash_key(raw: str) -> str: return hashlib.sha256(raw.encode()).hexdigest()
def daily_quota(plan: str, referrals: int) -> int:
    return PLAN_DAILY_QUOTA.get(plan, PLAN_DAILY_QUOTA["starter"]) + REFERRAL_BONUS_REQUESTS * min(referrals, REFERRAL_BONUS_CAP)

# ---- Webhooks: HMAC-SHA256 over "<timestamp>.<body>" (Stripe-style; receiver can reject replays) ----
def new_secret() -> str: return "whsec_" + secrets.token_hex(24)
def sign(secret: str, body: bytes, ts: int | None = None) -> tuple[str, int]:
    ts = ts or int(time.time()); mac = hmac.new(secret.encode(), str(ts).encode() + b"." + body, hashlib.sha256).hexdigest(); return f"t={ts},v1={mac}", ts
def verify(secret: str, body: bytes, header: str, tolerance_s: int = 300, now: float | None = None) -> bool:
    try: parts = dict(p.split("=", 1) for p in header.split(",")); ts = int(parts["t"]); v1 = parts["v1"]
    except Exception: return False
    if abs((now or time.time()) - ts) > tolerance_s: return False
    return hmac.compare_digest(sign(secret, body, ts)[0].split("v1=")[1], v1)
def webhook_body(event: str, listing: dict) -> bytes:
    return json.dumps({"event": event, "listing": listing, "sent_at": dt.datetime.now(dt.timezone.utc).isoformat()}, ensure_ascii=False, separators=(",", ":")).encode()

# ---- Referral codes: unambiguous alphabet, 8 chars ----
_ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
def new_code() -> str: return "".join(secrets.choice(_ALPHA) for _ in range(8))

# ---- Shareable deal links: token shown once, sha256 stored, expiring + revocable ----
def new_share_token() -> tuple[str, str]:
    t = secrets.token_urlsafe(24); return t, hashlib.sha256(t.encode()).hexdigest()
def public_listing(l) -> dict:
    """Sanitised view for strangers: no raw text/contact details, no user id, no notes."""
    ex = l.extracted or {}
    return {"score": l.score, "category": ex.get("category"), "location": ex.get("location"), "rooms": ex.get("rooms"), "price": ex.get("price"),
            "currency": ex.get("currency"), "condition": ex.get("condition"), "broker": ex.get("broker"), "risks": l.risks or [], "found_at": str(l.created_at)[:10]}

# ---- Weekly digest (plain text, Hebrew) ----
def build_digest(email: str, rows: list[dict], since_days: int = 7) -> tuple[str, str]:
    top = sorted(rows, key=lambda r: -r["score"])[:10]
    subj = f"Smart Sniper: {len(rows)} התאמות חדשות ב-{since_days} הימים האחרונים" if rows else "Smart Sniper: אין התאמות חדשות השבוע"
    lines = [f"שלום {email.split('@')[0]},", ""]
    if not top: lines.append("לא נמצאו התאמות חדשות השבוע. החיפושים שלך ממשיכים לרוץ.")
    for r in top:
        lines.append(f"• {r['score']}% | {r.get('location') or '?'} | {int(r['price']) if r.get('price') else '?'} ₪" + (f" | {r['verdict']}" if r.get("verdict") else ""))
    lines += ["", "לביטול הדיגסט: הגדרות > התראות."]
    return subj, "\n".join(lines)
