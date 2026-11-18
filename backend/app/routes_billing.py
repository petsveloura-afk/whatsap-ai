"""v3.15 payments: pay by card (PayPal Card Fields, no PayPal login) or PayPal, receipts, history, admin refunds.
Additive: registered in main.py inside try/except, so a problem here can never take the core API down.
The card number is typed into PayPal-hosted fields in the browser; this server only ever sees an order id."""
import logging, os
from decimal import Decimal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from . import billing, billing_core as bc, paypal
from . import main as _m   # late-bound: main swaps _m.limiter for the shared (DB) limiter on Postgres
from .db import get_db
from .models import User, Payment
from .routes_v2 import need, ADMIN

router = APIRouter(); log = logging.getLogger("sniper")


def _limit(key: str, n: int, window: int, msg: str = "יותר מדי ניסיונות, נסו שוב בעוד כמה דקות"):
    if not _m.limiter.allow(key, n, window): raise HTTPException(429, msg)
def _own(db: Session, u: User, pid: str) -> Payment:
    p = db.get(Payment, pid)
    if not p or p.customer_id != u.id: raise HTTPException(404, "Payment not found")   # same answer for "not yours" and "not there"
    return p


@router.get("/api/billing/config")
def billing_config(u: User = Depends(_m.current_user)):
    """What the checkout UI needs. The PayPal client id is public by design; the secret never leaves the server."""
    pc = paypal.public_config(); biz = bc.business()
    return {"paypal": pc, "available": paypal.configured(), "cards": pc["cards"], "currency": bc.currency(), "plans": bc.catalog(_m.PLANS),
            "subscriptions_available": bool(paypal.configured() and any(paypal.plan_ids().values())), "business_name": biz["name"], "receipt_title": biz["title"]}


class OrderIn(BaseModel):
    plan: str = Field(pattern="^(pro|vip)$")
    period: str = Field("monthly", pattern="^(monthly|yearly)$")
    method: str = Field("card", pattern="^(card|paypal)$")


@router.post("/api/billing/order")
def create_order(b: OrderIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    """Creates the payment record + PayPal order. The amount is computed HERE from the plan table; the browser cannot influence it."""
    if not paypal.configured() or (b.method == "card" and not paypal.cards_enabled()): raise HTTPException(503, "אמצעי התשלום אינו זמין כרגע")
    _limit("order:" + u.id, 12, 600)
    ok, why = bc.can_buy(billing.sub_view(billing.get_sub(db, u)), b.plan)
    if not ok: raise HTTPException(409, why)
    try: amount = bc.quote(b.plan, b.period, _m.PLANS)
    except ValueError: raise HTTPException(400, "Invalid plan")
    p = Payment(customer_id=u.id, customer_email=u.email, plan=b.plan, period=b.period, amount=amount, currency=bc.currency(), method=b.method, status="created")
    db.add(p); db.flush()   # id is needed as PayPal custom_id / invoice id / idempotency key
    try:
        p.paypal_order_id = paypal.create_order(amount, p.currency, p.id, p.id, bc.describe({"plan": p.plan, "period": p.period}), "order-" + p.id, card=b.method == "card")
    except Exception as e:
        p.status, p.failure_reason = "failed", ("paypal:" + (getattr(e, "issue", "") or type(e).__name__))[:200]; db.commit()
        log.warning("paypal create_order failed: %s %s", type(e).__name__, getattr(e, "debug_id", ""))
        raise HTTPException(502, "לא הצלחנו להתחיל את התשלום. לא חויבתם. נסו שוב בעוד רגע.")
    _m.audit(db, u, "billing.order_created", p.id, {"plan": b.plan, "period": b.period, "method": b.method, "amount": amount}); db.commit()
    return {"order_id": p.paypal_order_id, "payment_id": p.id, "amount": amount, "currency": p.currency}


def _done(p: Payment, db: Session) -> dict:
    s = billing.get_sub(db, p.customer_id)
    return {"status": p.status, "payment": billing.public(p), "plan": s.plan if s else None, "access_until": str(s.current_period_end) if s and s.current_period_end else None}


@router.post("/api/billing/order/{order_id}/capture")
def capture(order_id: str, bg: BackgroundTasks, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    """Called by the browser after the payer approved. Safe to call twice: PayPal-Request-Id makes the capture idempotent and completion is idempotent."""
    if not paypal.ORDER_ID_RE.match(order_id): raise HTTPException(404, "Payment not found")
    p = db.scalar(select(Payment).where(Payment.paypal_order_id == order_id, Payment.customer_id == u.id))
    if not p: raise HTTPException(404, "Payment not found")
    _limit("capture:" + u.id, 20, 600)
    if p.status == "completed": return _done(p, db)
    if p.status == "refunded": raise HTTPException(409, "התשלום הזה זוכה")
    try:
        order = paypal.capture_order(order_id, "capture-" + p.id)
    except paypal.PayPalError as e:
        if e.issue == "ORDER_ALREADY_CAPTURED":   # someone (webhook / earlier call) captured it: just read the final state
            try: order = paypal.get_order(order_id)
            except Exception: raise HTTPException(502, "מאמתים את התשלום. אל תשלמו שוב, נסו לרענן בעוד רגע.")
        elif e.status >= 500 or e.status == 429:   # outcome unknown: money may have moved. Do NOT mark failed, do NOT tell them to pay again.
            log.warning("capture outcome unknown payment=%s %s", p.id, e.debug_id)
            raise HTTPException(502, "לא קיבלנו אישור סופי מ-PayPal. אל תשלמו שוב. נסו שוב בעוד רגע; אם חויבתם, החבילה תופעל אוטומטית.")
        else:
            p.status, p.failure_reason = "failed", (e.issue or "declined")[:200]; db.commit()
            raise HTTPException(402, paypal.decline_message(e))
    except Exception:   # network error / timeout: same "unknown outcome" handling
        log.warning("capture network error payment=%s", p.id)
        raise HTTPException(502, "לא קיבלנו אישור סופי מ-PayPal. אל תשלמו שוב. נסו שוב בעוד רגע; אם חויבתם, החבילה תופעל אוטומטית.")
    info = bc.verify_capture(order, p.amount, p.currency, p.id)
    if info["pending"]:   # e.g. the card issuer / PayPal risk review holds it: activation happens from the COMPLETED webhook
        p.status, p.paypal_capture_id = "pending", info["capture_id"]; db.commit()
        return {"status": "pending", "message": "התשלום התקבל וממתין לאישור סופי. נעדכן ונפעיל את החבילה אוטומטית ברגע שיאושר.", "payment": billing.public(p)}
    if not info["ok"]:
        p.status, p.failure_reason = "failed", ("verify:" + info["reason"])[:200]; db.commit()
        log.error("capture verification failed payment=%s reason=%s", p.id, info["reason"])   # alert-worthy: money may need manual review
        raise HTTPException(409, "לא הצלחנו לאמת את התשלום. אם חויבתם, פנו אלינו ונטפל בכך מיד.")
    first = False
    for _ in range(3):   # IntegrityError = the webhook completed it first, or another receipt took the same number: re-read and retry
        try:
            first = billing.complete_payment(db, p, info); db.commit(); break
        except IntegrityError:
            db.rollback(); p = db.get(Payment, p.id)
            if p.status == "completed": first = False; break
    else: raise HTTPException(503, "התשלום התקבל אך ההפעלה נדחתה זמנית. אל תשלמו שוב, נסו לרענן בעוד רגע.")
    if first and (job := billing.mail_job(p)): bg.add_task(billing.send_job, job)
    return _done(p, db)


@router.get("/api/billing/payments")
def my_payments(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Payment).where(Payment.customer_id == u.id, Payment.status.in_(billing.VISIBLE)).order_by(Payment.created_at.desc()).limit(100)).all()
    return {"items": [billing.public(p) for p in rows]}


@router.get("/api/billing/receipt/{pid}")
def receipt(pid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    p = _own(db, u, pid)
    if p.status not in ("completed", "refunded"): raise HTTPException(409, "אין קבלה לתשלום שלא הושלם")
    return {"receipt_no": p.receipt_no, "html": bc.receipt_html(billing.receipt_dict(p))}


@router.post("/api/billing/receipt/{pid}/email")
def receipt_email(pid: str, bg: BackgroundTasks, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    p = _own(db, u, pid)
    if p.status not in ("completed", "refunded"): raise HTTPException(409, "אין קבלה לתשלום שלא הושלם")
    _limit("rcpt-mail:" + u.id, 5, 3600, "אפשר לשלוח קבלה במייל עד 5 פעמים בשעה")
    if not os.environ.get("SMTP_HOST"): raise HTTPException(503, "שליחת מייל אינה מוגדרת במערכת")
    p.customer_email = u.email   # always the CURRENT account address, never one supplied by the request
    bg.add_task(billing.send_job, billing.mail_job(p)); return {"ok": True}


# ---------------------------------------------------------------------------------------------------- admin
@router.get("/api/admin/billing/payments")
def admin_payments(status: str | None = None, a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    q = select(Payment).order_by(Payment.created_at.desc()).limit(200)
    if status: q = select(Payment).where(Payment.status == status).order_by(Payment.created_at.desc()).limit(200)
    rows = db.scalars(q).all()
    done = db.scalars(select(Payment).where(Payment.status == "completed")).all()
    total = sum((Decimal(x.amount) for x in done if x.currency == bc.currency()), Decimal(0))
    counts = dict(db.execute(select(Payment.status, func.count()).group_by(Payment.status)).all())
    return {"revenue_total": str(total.quantize(bc.CENT)), "currency": bc.currency(), "counts": counts,
            "items": [{**billing.public(p), "customer_email": p.customer_email, "customer_id": p.customer_id, "paypal_order_id": p.paypal_order_id,
                       "paypal_capture_id": p.paypal_capture_id, "failure_reason": p.failure_reason, "created_at": str(p.created_at)} for p in rows]}


class RefundIn(BaseModel): note: str = Field("", max_length=200)


@router.post("/api/admin/billing/payments/{pid}/refund")
def admin_refund(pid: str, b: RefundIn, a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    """Full refund through PayPal; removes the access this payment bought. Only for card/PayPal payments made through this system."""
    p = db.get(Payment, pid)
    if not p: raise HTTPException(404, "Payment not found")
    if p.status != "completed" or not p.paypal_capture_id or p.method == "subscription": raise HTTPException(409, "אי אפשר לזכות תשלום זה מכאן")
    _limit("refund:" + a.id, 20, 600)
    try: paypal.refund_capture(p.paypal_capture_id, "refund-" + p.id, note=b.note)
    except paypal.PayPalError as e:
        if e.issue != "CAPTURE_FULLY_REFUNDED": raise HTTPException(502, "PayPal דחה את ההחזר: " + (e.issue or str(e.status)))
    except Exception: raise HTTPException(502, "לא ניתן להגיע ל-PayPal כרגע")
    billing.revoke_for_refund(db, p)
    _m.audit(db, a, "billing.refund", p.id, {"amount": p.amount, "note": b.note}); db.commit()
    return {"ok": True, "payment": billing.public(p)}
