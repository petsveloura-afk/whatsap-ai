"""v3.17 e-mail verification (additive).
- Registration sends a one-time link (valid 24 h). Only a SHA-256 hash of the token is stored.
- Enforced ONLY when SMTP is configured (otherwise nobody could ever verify) and REQUIRE_EMAIL_VERIFICATION != 0.
- What is blocked until the address is confirmed: starting a payment (receipts are e-mailed there). Login and everything else keep working.
- Existing users are marked verified by the migration; admins / super admins are exempt (no lock-out of the owner).
"""
import datetime as dt, logging, os, secrets, threading
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import mail
from . import main as _m   # late-bound helpers (hashing, clock, audit, shared rate limiter)
from .db import get_db
from .models import User, EmailVerification

log = logging.getLogger("sniper")
router = APIRouter()
TTL = dt.timedelta(hours=24)
NEED_MSG = "יש לאמת את כתובת האימייל לפני תשלום. שלחנו לכם קישור אימות, ואפשר לבקש חדש באזור החשבון."


def required() -> bool:
    return bool(os.environ.get("SMTP_HOST")) and os.environ.get("REQUIRE_EMAIL_VERIFICATION", "1") != "0"


def is_verified(u: User) -> bool:
    return u.email_verified_at is not None or u.role in ("admin", "super_admin") or not required()


def status(u: User) -> dict:
    return {"email_verified": is_verified(u), "verification_required": required()}


def _link(raw: str) -> str:
    return os.environ.get("APP_URL", "").rstrip("/") + "/?verify=" + raw


def issue(db: Session, u: User) -> str:
    """New token; older unused tokens of this user stop working."""
    for r in db.scalars(select(EmailVerification).where(EmailVerification.user_id == u.id, EmailVerification.used.is_(False))).all():
        r.used = True
    raw = secrets.token_urlsafe(32)
    db.add(EmailVerification(user_id=u.id, token_hash=_m._h(raw), expires_at=dt.datetime.now(dt.timezone.utc) + TTL)); db.commit()
    return raw


def _send(to: str, link: str) -> None:
    text = f"שלום,\n\nכדי לאמת את כתובת האימייל שלכם ב-Smart Sniper AI פתחו את הקישור (תקף ל-24 שעות):\n{link}\n\nאם לא נרשמתם, אפשר להתעלם מההודעה."
    html = ('<div dir="rtl" style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:auto;padding:20px;line-height:1.6">'
            '<h2 style="margin:0 0 8px">אימות כתובת אימייל</h2><p>כדי להשלים את ההרשמה ל-Smart Sniper AI לחצו על הכפתור. הקישור תקף ל-24 שעות.</p>'
            f'<p style="margin:22px 0"><a href="{link}" style="background:#0891b2;color:#fff;padding:12px 22px;border-radius:10px;text-decoration:none;font-weight:700">אימות האימייל</a></p>'
            f'<p style="color:#6b7280;font-size:13px">אם הכפתור לא עובד, העתיקו את הכתובת לדפדפן:<br><span dir="ltr">{link}</span></p>'
            '<p style="color:#6b7280;font-size:13px">אם לא נרשמתם, אפשר להתעלם מההודעה.</p></div>')

    def run():
        try: mail.send_mail(to, "אימות כתובת האימייל שלך - Smart Sniper AI", text, html)
        except Exception as e: log.warning("verification mail failed: %s", type(e).__name__)
    threading.Thread(target=run, daemon=True).start()   # SMTP can take seconds: never make the user wait for it


def start(db: Session, u: User) -> None:
    if not required() or is_verified(u): return
    _send(u.email, _link(issue(db, u)))


class VerifyIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


@router.post("/api/auth/verify-email")
def verify_email(b: VerifyIn, db: Session = Depends(get_db)):
    if not _m.limiter.allow("verify-try", 60, 60): raise HTTPException(429, "יותר מדי ניסיונות. נסו שוב בעוד דקה")
    r = db.scalar(select(EmailVerification).where(EmailVerification.token_hash == _m._h(b.token)))
    if not r or r.used or r.expires_at.replace(tzinfo=None) < _m._now(): raise HTTPException(400, "קישור האימות אינו תקף או שפג תוקפו. אפשר לבקש קישור חדש באזור החשבון.")
    u = db.get(User, r.user_id)
    if not u or not u.is_active: raise HTTPException(400, "קישור האימות אינו תקף")
    r.used = True
    if u.email_verified_at is None: u.email_verified_at = dt.datetime.now(dt.timezone.utc)
    _m.audit(db, u, "auth.email_verified", u.id); db.commit()
    return {"ok": True, "email": u.email}


@router.post("/api/auth/resend-verification", status_code=202)
def resend(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    if is_verified(u): return {"ok": True, "already_verified": True}
    if not os.environ.get("SMTP_HOST"): raise HTTPException(503, "שליחת מייל אינה מוגדרת במערכת")
    if not _m.limiter.allow("verify-cd:" + u.id, 1, 60): raise HTTPException(429, "המתינו דקה לפני בקשה נוספת")
    if not _m.limiter.allow("verify-hr:" + u.id, 5, 3600): raise HTTPException(429, "יותר מדי בקשות. נסו שוב מאוחר יותר")
    _send(u.email, _link(issue(db, u)))
    return {"ok": True}
