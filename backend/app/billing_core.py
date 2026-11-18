"""v3.15 billing core: PURE logic (no database, no web framework), so every rule that touches money is unit-testable.

Rules enforced here, never in the browser:
  * the amount is always computed on the server from the plan table (a client can send a plan + period, never a price);
  * a PayPal capture is accepted only if status, amount, currency and our own payment id all match what we asked for;
  * amounts are Decimal / decimal strings, never floats.
"""
import datetime as dt, html, os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

PERIOD_DAYS = {"monthly": 30, "yearly": 365}
PERIOD_HE = {"monthly": "חודשי", "yearly": "שנתי"}
PLAN_HE = {"starter": "Starter", "pro": "Pro", "vip": "VIP"}
METHOD_HE = {"card": "כרטיס אשראי", "paypal": "PayPal", "subscription": "מנוי PayPal מתחדש"}
CENT = Decimal("0.01")


def utcnow() -> dt.datetime: return dt.datetime.now(dt.timezone.utc)
def utc(d: dt.datetime | None) -> dt.datetime | None:
    """Treat naive datetimes (SQLite) as UTC so comparisons never mix naive and aware values."""
    if d is None: return None
    return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d.astimezone(dt.timezone.utc)
def expired(period_end: dt.datetime | None, now: dt.datetime | None = None) -> bool:
    """NULL period end = recurring subscription managed by PayPal webhooks = never expires by date."""
    return period_end is not None and utc(period_end) <= (now or utcnow())


# ---------------------------------------------------------------------------------------------------- pricing
def yearly_months() -> int:
    try: return max(1, min(12, int(os.environ.get("BILLING_YEARLY_MONTHS", "10"))))   # default: pay 10 months, get 12
    except ValueError: return 10
def currency() -> str:
    c = os.environ.get("BILLING_CURRENCY", "ILS").upper()
    return c if len(c) == 3 and c.isalpha() else "ILS"
def _price(plan: str, plans: dict) -> Decimal:
    if plan not in plans or plan == "starter": raise ValueError("unknown or free plan")
    try: p = Decimal(str(plans[plan]["price"]))
    except (InvalidOperation, KeyError): raise ValueError("bad price")
    if p <= 0: raise ValueError("unknown or free plan")
    return p
def quote(plan: str, period: str, plans: dict) -> str:
    """Server-side price for plan+period as a 2-decimal string, e.g. '99.00'."""
    if period not in PERIOD_DAYS: raise ValueError("unknown period")
    p = _price(plan, plans) * (yearly_months() if period == "yearly" else 1)
    return str(p.quantize(CENT, ROUND_HALF_UP))
def monthly_value(plan: str, period: str, plans: dict) -> float:
    """Revenue-per-month contribution of a subscription (yearly prepaid counts 1/12 of what was charged)."""
    try: p = _price(plan, plans)
    except ValueError: return 0.0
    return float(p * yearly_months() / 12) if period == "yearly" else float(p)
def catalog(plans: dict) -> list[dict]:
    out = []
    for k, v in plans.items():
        if k == "starter": continue
        m = quote(k, "monthly", plans); y = quote(k, "yearly", plans)
        out.append({"id": k, "name": PLAN_HE.get(k, k), "monthly": m, "yearly": y, "yearly_months": yearly_months(),
                    "yearly_saving": str((Decimal(m) * 12 - Decimal(y)).quantize(CENT)), "max_searches": v.get("max_searches")})
    return out


# ---------------------------------------------------------------------------------------------------- entitlement
def can_buy(sub: dict | None, plan: str, now: dt.datetime | None = None) -> tuple[bool, str]:
    """sub = {plan, status, current_period_end, paypal_subscription_id} or None. -> (allowed, hebrew reason)."""
    now = now or utcnow()
    if not sub or sub.get("status") != "active": return True, ""
    end = sub.get("current_period_end")
    if end is None: return False, "יש לך מנוי מתחדש פעיל דרך PayPal. לניהולו היכנסו לחשבון ה-PayPal שלכם או בטלו אותו כאן."
    if expired(end, now): return True, ""
    if sub.get("plan") != plan: return False, "יש לך חבילה פעילה אחרת. אפשר לחדש רק את אותה חבילה עד שהיא מסתיימת."
    return True, ""
def extend(now: dt.datetime, current_end: dt.datetime | None, same_plan_active: bool, period: str) -> tuple[dt.datetime, dt.datetime]:
    """Renewing before expiry stacks the new period after the remaining time (the customer never loses paid days)."""
    cur = utc(current_end)
    start = cur if (same_plan_active and cur and cur > now) else now
    return start, start + dt.timedelta(days=PERIOD_DAYS[period])


# ---------------------------------------------------------------------------------------------------- capture verification
def _dec(v) -> Decimal | None:
    try: return Decimal(str(v))
    except (InvalidOperation, TypeError): return None
def verify_capture(order: dict, expected_amount: str, expected_currency: str, expected_custom_id: str) -> dict:
    """Validates a PayPal order object returned by capture/get. -> {ok, pending, reason, capture_id, payer_email, brand, last4, liability_shift}.
    ok=True only for a COMPLETED capture whose amount, currency and custom_id all match what the server asked for."""
    res = {"ok": False, "pending": False, "reason": "", "capture_id": None, "payer_email": None, "brand": None, "last4": None, "liability_shift": None}
    try:
        pu = (order.get("purchase_units") or [{}])[0]
        caps = ((pu.get("payments") or {}).get("captures") or [])
        cap = caps[0] if caps else None
        res["payer_email"] = ((order.get("payer") or {}).get("email_address") or None)
        card = ((order.get("payment_source") or {}).get("card") or {})
        res["brand"] = (card.get("brand") or None); l4 = str(card.get("last_digits") or "")[-4:]
        res["last4"] = l4 if l4.isdigit() and len(l4) == 4 else None
        res["liability_shift"] = (((card.get("authentication_result") or {}).get("liability_shift")) or None)
        if not cap: res["reason"] = "no capture in order"; return res
        res["capture_id"] = cap.get("id")
        if pu.get("custom_id") and pu["custom_id"] != expected_custom_id: res["reason"] = "custom_id mismatch"; return res
        amt = cap.get("amount") or {}
        a, e = _dec(amt.get("value")), _dec(expected_amount)
        if a is None or e is None or a != e: res["reason"] = "amount mismatch"; return res
        if (amt.get("currency_code") or "").upper() != expected_currency.upper(): res["reason"] = "currency mismatch"; return res
        st = (cap.get("status") or "").upper()
        if st == "PENDING": res["pending"] = True; res["reason"] = "capture pending"; return res
        if st != "COMPLETED" or (order.get("status") or "").upper() not in ("COMPLETED", "APPROVED", ""): res["reason"] = f"capture status {st or '?'}"; return res
        if not res["capture_id"]: res["reason"] = "no capture id"; return res
        res["ok"] = True; return res
    except Exception as e:   # malformed payload must never activate anything
        res["reason"] = "malformed order: " + type(e).__name__; return res


# ---------------------------------------------------------------------------------------------------- business details + receipts
def business() -> dict:
    def f(k, d=""): return (os.environ.get(k) or d).strip()
    try: vat = max(0.0, min(0.5, float(os.environ.get("VAT_RATE", "0") or 0)))
    except ValueError: vat = 0.0
    return {"name": f("BUSINESS_NAME", "Smart Sniper AI"), "id": f("BUSINESS_ID"), "address": f("BUSINESS_ADDRESS"), "email": f("BUSINESS_EMAIL"),
            "phone": f("BUSINESS_PHONE"), "vat_rate": vat, "title": f("RECEIPT_TITLE", "אישור תשלום"), "prefix": f("RECEIPT_PREFIX", "SS") or "SS",
            "footer": f("RECEIPT_FOOTER")}
def vat_breakdown(total: str, rate: float) -> tuple[str, str] | None:
    """Prices are VAT-inclusive. Returns (net, vat) strings or None when no VAT rate is configured."""
    if not rate: return None
    t = _dec(total)
    if t is None: return None
    net = (t / (Decimal(1) + Decimal(str(rate)))).quantize(CENT, ROUND_HALF_UP)
    return str(net), str((t - net).quantize(CENT, ROUND_HALF_UP))
def next_receipt_no(prefix: str, last: str | None) -> str:
    """Continuous numbering (no gaps / no yearly reset): SS-000001, SS-000002 ..."""
    n = 0
    if last:
        tail = last.rsplit("-", 1)[-1]
        if tail.isdigit(): n = int(tail)
    return f"{prefix}-{n + 1:06d}"
def _jerusalem(d: dt.datetime | None) -> dt.datetime | None:
    d = utc(d)
    if d is None: return None
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("Asia/Jerusalem"))
    except Exception: return d + dt.timedelta(hours=2)   # tzdata missing on a slim image: fixed UTC+2 is closer than UTC
def fmt_date(d: dt.datetime | None) -> str:
    j = _jerusalem(d); return j.strftime("%d/%m/%Y") if j else ""
def fmt_dt(d: dt.datetime | None) -> str:
    j = _jerusalem(d); return j.strftime("%d/%m/%Y %H:%M") if j else ""
def describe(p: dict) -> str:
    return f"Smart Sniper AI · חבילת {PLAN_HE.get(p['plan'], p['plan'])} ({PERIOD_HE.get(p['period'], p['period'])})"
def method_label(p: dict) -> str:
    if p.get("method") == "card":
        return "כרטיס אשראי" + (f" {p['card_brand']} ••••{p['card_last4']}" if p.get("card_brand") and p.get("card_last4") else (f" ••••{p['card_last4']}" if p.get("card_last4") else ""))
    return METHOD_HE.get(p.get("method"), p.get("method") or "")
def money(amount: str, cur: str) -> str:
    sym = {"ILS": "₪", "USD": "$", "EUR": "€"}.get(cur.upper())
    return f"{sym}{amount}" if sym == "$" or sym == "€" else (f"{amount} {sym}" if sym else f"{amount} {cur}")


def receipt_html(p: dict, biz: dict | None = None) -> str:
    """Self-contained, printable, RTL receipt. EVERY dynamic value is HTML-escaped."""
    b = biz or business(); e = html.escape
    rows = [("תיאור", describe(p)), ("אמצעי תשלום", method_label(p))]
    if p.get("period_start") and p.get("period_end"): rows.append(("תקופת שימוש", f"{fmt_date(p['period_start'])} – {fmt_date(p['period_end'])}"))
    if p.get("payer_email"): rows.append(("חשבון משלם", p["payer_email"]))
    rows += [("מזהה עסקה PayPal", p.get("paypal_capture_id") or ""), ("מזהה הזמנה", p.get("paypal_order_id") or "")]
    vb = vat_breakdown(p["amount"], b["vat_rate"])
    totals = ""
    if vb: totals += f"<tr><td>סכום לפני מע״מ</td><td>{e(money(vb[0], p['currency']))}</td></tr><tr><td>מע״מ ({e(str(round(b['vat_rate'] * 100, 2)).rstrip('0').rstrip('.'))}%)</td><td>{e(money(vb[1], p['currency']))}</td></tr>"
    totals += f"<tr class='tot'><td>סה״כ שולם</td><td>{e(money(p['amount'], p['currency']))}</td></tr>"
    refunded = "<div class='stamp'>זוכה – הסכום הוחזר</div>" if p.get("status") == "refunded" else ""
    meta = " · ".join(e(x) for x in (f"ח.פ./ע.מ. {b['id']}" if b["id"] else "", b["address"], b["email"], b["phone"]) if x)
    return f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(b['title'])} {e(p.get('receipt_no') or '')}</title><style>
body{{font-family:Heebo,Arial,sans-serif;color:#111;background:#f3f4f6;margin:0;padding:24px}}
.sheet{{max-width:680px;margin:auto;background:#fff;border:1px solid #d1d5db;border-radius:10px;padding:32px;position:relative}}
h1{{font-size:1.5rem;margin:0 0 .2rem}}.biz{{color:#555;font-size:.9rem;margin-bottom:1.2rem}}
.head{{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;border-bottom:2px solid #111;padding-bottom:.8rem;margin-bottom:1rem}}
.no{{font-family:monospace;font-size:1.1rem;font-weight:700}}table{{width:100%;border-collapse:collapse}}td{{padding:.55rem .3rem;border-bottom:1px solid #e5e7eb;vertical-align:top}}
td:first-child{{color:#555;width:38%}}td:last-child{{word-break:break-word}}.tot td{{font-size:1.2rem;font-weight:800;border-bottom:0;border-top:2px solid #111}}
.stamp{{position:absolute;inset-block-start:2rem;inset-inline-end:2rem;color:#b91c1c;border:3px solid #b91c1c;padding:.3rem .8rem;transform:rotate(-8deg);font-weight:800}}
.note{{color:#666;font-size:.8rem;margin-top:1.2rem}}button{{margin:1rem auto 0;display:block;padding:.6rem 1.4rem;border-radius:8px;border:0;background:#111;color:#fff;font-size:1rem;cursor:pointer}}
@media print{{body{{background:#fff;padding:0}}.sheet{{border:0}}button{{display:none}}}}</style></head><body><div class="sheet">{refunded}
<div class="head"><div><h1>{e(b['title'])}</h1><div class="biz"><b>{e(b['name'])}</b><br>{meta}</div></div>
<div><div class="no">{e(p.get('receipt_no') or '')}</div><div>תאריך: {e(fmt_dt(p.get('paid_at')))}</div></div></div>
<table>{''.join(f"<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>" for k, v in rows if v)}</table>
<table style="margin-top:.6rem">{totals}</table>
<div class="note">{e(b['footer']) if b['footer'] else 'מסמך זה מהווה אישור על קבלת התשלום.'} פרטי הכרטיס המלאים אינם נשמרים אצלנו.</div>
<button onclick="window.print()">הדפסה / שמירה כ-PDF</button></div></body></html>"""


def receipt_email(p: dict, biz: dict | None = None) -> tuple[str, str, str]:
    """-> (subject, plain text, html). The same escaped receipt is the HTML body."""
    b = biz or business()
    subj = f"{b['title']} {p.get('receipt_no') or ''} · {b['name']}".strip()
    lines = [f"תודה על התשלום! החבילה שלך פעילה.", "", f"{b['title']}: {p.get('receipt_no') or ''}", f"תיאור: {describe(p)}",
             f"סכום: {money(p['amount'], p['currency'])}", f"אמצעי תשלום: {method_label(p)}"]
    if p.get("period_end"): lines.append(f"פעיל עד: {fmt_date(p['period_end'])}")
    lines += ["", "אפשר להוריד את הקבלה בכל עת מאזור החשבון באתר.", f"{b['name']}"]
    return subj, "\n".join(lines), receipt_html(p, b)
