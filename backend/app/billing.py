"""v3.15 billing, database side. Everything here is idempotent: PayPal retries webhooks and browsers retry requests, so
completing the same payment twice must never create a second receipt or extend access twice."""
import datetime as dt, logging
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import billing_core as bc
from .models import User, Subscription, Payment, AuditLog
from .models2 import Notification

log = logging.getLogger("sniper")
VISIBLE = ("completed", "refunded", "pending")   # statuses a customer sees in their history


def public(p: Payment) -> dict:
    """Customer-facing view of a payment (no internal ids of other systems beyond the PayPal transaction id printed on the receipt)."""
    return {"id": p.id, "receipt_no": p.receipt_no, "plan": p.plan, "period": p.period, "amount": p.amount, "currency": p.currency, "method": p.method,
            "card_brand": p.card_brand, "card_last4": p.card_last4, "status": p.status, "paid_at": str(p.paid_at) if p.paid_at else None,
            "period_start": str(p.period_start) if p.period_start else None, "period_end": str(p.period_end) if p.period_end else None}
def receipt_dict(p: Payment) -> dict:
    return {**public(p), "payer_email": p.payer_email, "paypal_capture_id": p.paypal_capture_id, "paypal_order_id": p.paypal_order_id,
            "paid_at": p.paid_at, "period_start": p.period_start, "period_end": p.period_end}   # real datetimes for the renderer
def get_sub(db: Session, uid: str) -> Subscription | None: return db.scalar(select(Subscription).where(Subscription.user_id == uid))
def sub_view(s: Subscription | None) -> dict | None:
    return None if not s else {"plan": s.plan, "status": s.status, "current_period_end": s.current_period_end, "paypal_subscription_id": s.paypal_subscription_id}


def _assign_receipt_no(db: Session, p: Payment) -> None:
    """Next continuous number. The UNIQUE constraint is the real guard: two concurrent completions can compute the same number, one of them
    fails at commit with IntegrityError and its caller retries (routes_billing.capture) or lets PayPal re-deliver the webhook."""
    prefix = bc.business()["prefix"]
    last = db.scalar(select(Payment.receipt_no).where(Payment.receipt_no.like(prefix + "-%")).order_by(Payment.receipt_no.desc()).limit(1))
    p.receipt_no = bc.next_receipt_no(prefix, last)


def notify(db: Session, uid: str, title: str, body: str) -> None:
    db.add(Notification(user_id=uid, title=title[:200], body=body[:500]))
def _audit(db: Session, actor: str | None, action: str, target: str, detail: dict) -> None:
    db.add(AuditLog(actor_id=actor, action=action, target=target, detail=detail))


def complete_payment(db: Session, p: Payment, info: dict, now: dt.datetime | None = None) -> bool:
    """Marks a verified capture as paid, grants/extends access, allocates the receipt number, records audit + in-app notification.
    Returns True only the first time (so the caller sends the receipt e-mail exactly once). The caller commits."""
    if p.status == "completed": return False
    if p.status == "refunded": return False   # a refund event must not be undone by a late/duplicate 'completed'
    now = now or bc.utcnow()
    p.status, p.paid_at, p.failure_reason = "completed", now, None
    p.paypal_capture_id = info.get("capture_id") or p.paypal_capture_id
    p.payer_email = info.get("payer_email") or p.payer_email
    p.card_brand = (info.get("brand") or p.card_brand or None)
    p.card_last4 = info.get("last4") or p.card_last4
    user = db.get(User, p.customer_id)
    if user and p.method != "subscription":   # recurring PayPal subscriptions are activated by their own webhook, not by a receipt
        s = get_sub(db, user.id)
        if not s: s = Subscription(user_id=user.id); db.add(s)
        same = bool(s.status == "active" and s.plan == p.plan and s.current_period_end is not None)
        p.period_start, p.period_end = bc.extend(now, s.current_period_end, same, p.period)
        s.plan, s.status, s.current_period_end, s.billing_period, s.renewal_reminded_at = p.plan, "active", p.period_end, p.period, None
        s.paypal_subscription_id = None   # an abandoned/pending recurring checkout must not later cancel prepaid access
        notify(db, user.id, "התשלום התקבל ✓", f"חבילת {bc.PLAN_HE.get(p.plan, p.plan)} פעילה עד {bc.fmt_date(p.period_end)}. הקבלה זמינה באזור החשבון.")
    _assign_receipt_no(db, p)
    _audit(db, p.customer_id, "billing.payment_completed", p.id, {"plan": p.plan, "period": p.period, "amount": p.amount, "currency": p.currency, "method": p.method, "receipt": p.receipt_no})
    return True


def revoke_for_refund(db: Session, p: Payment, now: dt.datetime | None = None) -> None:
    """Refund/chargeback: remove exactly the time that this payment bought. The caller commits."""
    now = now or bc.utcnow()
    p.status, p.refunded_at = "refunded", now
    s = get_sub(db, p.customer_id)
    if s and s.current_period_end is not None and p.period_start and p.period_end:
        new_end = bc.utc(s.current_period_end) - (bc.utc(p.period_end) - bc.utc(p.period_start))
        if new_end <= now: s.status, s.current_period_end = "canceled", now
        else: s.current_period_end = new_end
    if db.get(User, p.customer_id): notify(db, p.customer_id, "התשלום זוכה", f"התשלום על חבילת {bc.PLAN_HE.get(p.plan, p.plan)} ({p.receipt_no or ''}) הוחזר.")
    _audit(db, None, "billing.payment_refunded", p.id, {"amount": p.amount, "receipt": p.receipt_no})


def mail_job(p: Payment) -> dict | None:
    """Everything needed to e-mail the receipt, as plain strings (safe to hand to a background task after the session closes)."""
    if not p.customer_email: return None
    subj, text, html = bc.receipt_email(receipt_dict(p))
    return {"to": p.customer_email, "subject": subj, "text": text, "html": html}
def send_job(job: dict | None) -> None:
    if not job: return
    try:
        from . import mail
        mail.send_mail(job["to"], job["subject"], job["text"], job.get("html"))
    except Exception as e: log.warning("receipt mail failed: %s", type(e).__name__)   # never leak the address into logs


# ---------------------------------------------------------------------------------------------------- PayPal webhook events
def _find_for_capture(db: Session, r: dict) -> Payment | None:
    cid = r.get("custom_id")
    p = db.get(Payment, cid) if cid and len(str(cid)) <= 36 else None
    if p: return p
    oid = ((r.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
    if oid: return db.scalar(select(Payment).where(Payment.paypal_order_id == oid))
    return db.scalar(select(Payment).where(Payment.paypal_capture_id == r.get("id"))) if r.get("id") else None


def handle_webhook(db: Session, event_type: str, r: dict) -> list[dict]:
    """Applies a signature-verified PayPal event to payments. -> list of receipt mail jobs to send after commit. Unknown events: no-op."""
    jobs: list[dict] = []
    if event_type in ("PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.PENDING", "PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.DECLINED"):
        p = _find_for_capture(db, r)
        if not p: return jobs
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            amt = r.get("amount") or {}
            try: same = Decimal(str(amt.get("value"))) == Decimal(p.amount) and str(amt.get("currency_code", "")).upper() == p.currency.upper()
            except Exception: same = False
            if not same: log.error("webhook capture amount mismatch payment=%s", p.id); return jobs   # never activate on a mismatch
            if complete_payment(db, p, {"capture_id": r.get("id")}):
                j = mail_job(p)
                if j: jobs.append(j)
        elif event_type == "PAYMENT.CAPTURE.PENDING":
            if p.status == "created": p.status = "pending"; p.paypal_capture_id = p.paypal_capture_id or r.get("id")
        elif p.status in ("created", "pending"):
            p.status, p.failure_reason = "failed", "capture " + event_type.rsplit(".", 1)[-1].lower()
    elif event_type in ("PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"):
        # a refund event's resource is the refund, whose links point at the capture; fall back to matching by capture id
        cap_id = r.get("id") if event_type.endswith("REVERSED") else next((l["href"].rstrip("/").rsplit("/", 1)[-1] for l in r.get("links", []) if l.get("rel") == "up"), None)
        p = db.scalar(select(Payment).where(Payment.paypal_capture_id == cap_id)) if cap_id else None
        if p and p.status == "completed":
            try: partial = event_type.endswith("REFUNDED") and (r.get("amount") or {}).get("value") is not None and Decimal(str(r["amount"]["value"])) < Decimal(p.amount)
            except Exception: partial = False
            if partial: log.warning("partial refund payment=%s: access unchanged, review manually", p.id); _audit(db, None, "billing.partial_refund", p.id, {"refunded": r["amount"]["value"], "amount": p.amount})
            else: revoke_for_refund(db, p)
    elif event_type == "PAYMENT.SALE.COMPLETED":   # a renewal charge of the recurring PayPal subscription -> receipt
        sub_id = r.get("billing_agreement_id"); sale_id = r.get("id")
        s = db.scalar(select(Subscription).where(Subscription.paypal_subscription_id == sub_id)) if sub_id else None
        if not s or not sale_id or db.scalar(select(Payment.id).where(Payment.paypal_capture_id == sale_id)): return jobs
        u = db.get(User, s.user_id)
        if not u: return jobs
        amt = r.get("amount") or {}
        try: total = str(Decimal(str(amt.get("total", "0"))).quantize(bc.CENT))
        except Exception: log.warning("sale event with bad amount ignored"); return jobs
        p = Payment(customer_id=u.id, customer_email=u.email, plan=s.plan, period="monthly", amount=total,
                    currency=str(amt.get("currency", bc.currency())).upper()[:3], method="subscription", status="created", paypal_order_id=None)
        db.add(p); db.flush()
        if complete_payment(db, p, {"capture_id": sale_id}):
            j = mail_job(p)
            if j: jobs.append(j)
    return jobs


# ---------------------------------------------------------------------------------------------------- scheduler hook
def housekeeping(db: Session, days_before: int = 3) -> dict:
    """Run by the worker scheduler. (1) one renewal reminder per prepaid period, (2) expire stale unfinished payment attempts."""
    now = bc.utcnow(); n = 0
    soon = now + dt.timedelta(days=days_before)
    for s in db.scalars(select(Subscription).where(Subscription.status == "active", Subscription.current_period_end.is_not(None), Subscription.renewal_reminded_at.is_(None))):
        end = bc.utc(s.current_period_end)
        if now < end <= soon:
            notify(db, s.user_id, "החבילה שלך מסתיימת בקרוב", f"חבילת {bc.PLAN_HE.get(s.plan, s.plan)} פעילה עד {bc.fmt_date(end)}. אפשר לחדש מאזור החשבון.")
            s.renewal_reminded_at = now; n += 1
    cutoff = now - dt.timedelta(hours=24); stale = 0
    for p in db.scalars(select(Payment).where(Payment.status == "created", Payment.created_at < cutoff)):
        p.status, p.failure_reason = "failed", "abandoned"; stale += 1   # a never-captured order can still be captured later only via a new order
    return {"reminders": n, "abandoned": stale}
