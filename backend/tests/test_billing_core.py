"""v3.15 billing: pure money rules (no database, no network)."""
import datetime as dt, os
from app import billing_core as bc
PLANS = {"starter": {"price": 0, "max_searches": 3}, "pro": {"price": 99, "max_searches": 15}, "vip": {"price": 149, "max_searches": 50}}
NOW = dt.datetime(2026, 11, 17, 12, 0, tzinfo=dt.timezone.utc)

def test_quote_is_server_side_and_decimal():
    assert bc.quote("pro", "monthly", PLANS) == "99.00" and bc.quote("vip", "monthly", PLANS) == "149.00"
    assert bc.quote("pro", "yearly", PLANS) == "990.00"          # 10 months charged by default
    for bad in (("starter", "monthly"), ("nope", "monthly"), ("pro", "weekly")):
        try: bc.quote(*bad, PLANS); assert False, bad
        except ValueError: pass
def test_yearly_months_env_is_clamped():
    os.environ["BILLING_YEARLY_MONTHS"] = "99"; assert bc.yearly_months() == 12
    os.environ["BILLING_YEARLY_MONTHS"] = "abc"; assert bc.yearly_months() == 10
    os.environ.pop("BILLING_YEARLY_MONTHS")
def test_monthly_value_for_mrr():
    assert bc.monthly_value("pro", "monthly", PLANS) == 99.0 and round(bc.monthly_value("pro", "yearly", PLANS), 2) == 82.5 and bc.monthly_value("starter", "monthly", PLANS) == 0.0

def _order(value="99.00", cur="ILS", cap="COMPLETED", custom="PAY1", status="COMPLETED"):
    return {"id": "ORD1", "status": status, "payer": {"email_address": "p@x.com"}, "payment_source": {"card": {"brand": "VISA", "last_digits": "4242"}},
            "purchase_units": [{"custom_id": custom, "payments": {"captures": [{"id": "CAP1", "status": cap, "amount": {"value": value, "currency_code": cur}}]}}]}
def test_verify_capture_accepts_exact_match():
    r = bc.verify_capture(_order(), "99.00", "ILS", "PAY1")
    assert r["ok"] and r["capture_id"] == "CAP1" and r["brand"] == "VISA" and r["last4"] == "4242" and r["payer_email"] == "p@x.com"
    assert bc.verify_capture(_order("99"), "99.00", "ILS", "PAY1")["ok"]     # 99 == 99.00 numerically
def test_verify_capture_rejects_everything_else():
    assert not bc.verify_capture(_order("1.00"), "99.00", "ILS", "PAY1")["ok"]            # underpaid
    assert not bc.verify_capture(_order(cur="USD"), "99.00", "ILS", "PAY1")["ok"]         # wrong currency
    assert not bc.verify_capture(_order(custom="OTHER"), "99.00", "ILS", "PAY1")["ok"]    # someone else's payment
    assert not bc.verify_capture(_order(cap="DECLINED"), "99.00", "ILS", "PAY1")["ok"]
    assert not bc.verify_capture({}, "99.00", "ILS", "PAY1")["ok"] and not bc.verify_capture({"purchase_units": "x"}, "99.00", "ILS", "PAY1")["ok"]
    p = bc.verify_capture(_order(cap="PENDING"), "99.00", "ILS", "PAY1"); assert p["pending"] and not p["ok"]
def test_bad_last4_is_dropped():
    o = _order(); o["payment_source"]["card"]["last_digits"] = "<b>"; assert bc.verify_capture(o, "99.00", "ILS", "PAY1")["last4"] is None

def test_can_buy_rules():
    act = lambda **k: {"status": "active", "plan": "pro", "current_period_end": NOW + dt.timedelta(days=5), **k}
    assert bc.can_buy(None, "pro", NOW)[0] and bc.can_buy({"status": "pending", "plan": "pro"}, "vip", NOW)[0]
    assert bc.can_buy(act(), "pro", NOW)[0]                                  # renew same plan early
    assert not bc.can_buy(act(), "vip", NOW)[0]                              # no plan switch while paid time remains
    assert bc.can_buy(act(current_period_end=NOW - dt.timedelta(days=1)), "vip", NOW)[0]   # expired -> free to buy anything
    assert not bc.can_buy(act(current_period_end=None), "pro", NOW)[0]       # live recurring PayPal subscription
def test_extend_stacks_remaining_days_and_naive_dates_are_utc():
    s, e = bc.extend(NOW, NOW + dt.timedelta(days=5), True, "monthly"); assert s == NOW + dt.timedelta(days=5) and e - s == dt.timedelta(days=30)
    s, e = bc.extend(NOW, NOW + dt.timedelta(days=5), False, "yearly"); assert s == NOW and e - s == dt.timedelta(days=365)
    s, _ = bc.extend(NOW, (NOW + dt.timedelta(days=2)).replace(tzinfo=None), True, "monthly"); assert s == NOW + dt.timedelta(days=2)   # SQLite returns naive
    assert bc.expired(NOW - dt.timedelta(seconds=1), NOW) and not bc.expired(None, NOW) and not bc.expired(NOW + dt.timedelta(seconds=1), NOW)

def _pay(**k):
    return {"receipt_no": "SS-000007", "plan": "pro", "period": "monthly", "amount": "99.00", "currency": "ILS", "method": "card", "card_brand": "VISA", "card_last4": "4242",
            "status": "completed", "paid_at": NOW, "period_start": NOW, "period_end": NOW + dt.timedelta(days=30), "payer_email": "p@x.com", "paypal_capture_id": "CAP1", "paypal_order_id": "ORD1", **k}
def test_receipt_escapes_everything_and_shows_the_facts():
    h = bc.receipt_html(_pay(payer_email="<script>alert(1)</script>", card_brand="<img src=x onerror=1>"))
    assert "<script>alert(1)</script>" not in h and "&lt;script&gt;" in h and "<img src=x" not in h
    assert "SS-000007" in h and "99.00 ₪" in h
    assert "17/11/2026" in h and "17/12/2026" in h
def test_receipt_vat_and_refund_stamp():
    os.environ["VAT_RATE"] = "0.18"
    try:
        assert bc.vat_breakdown("118.00", 0.18) == ("100.00", "18.00")
        h = bc.receipt_html(_pay(amount="118.00", status="refunded")); assert "סכום לפני מע״מ" in h and "זוכה" in h
    finally: os.environ.pop("VAT_RATE")
    assert bc.vat_breakdown("99.00", 0.0) is None and "מע״מ" not in bc.receipt_html(_pay())
def test_receipt_numbers_are_continuous():
    assert bc.next_receipt_no("SS", None) == "SS-000001" and bc.next_receipt_no("SS", "SS-000009") == "SS-000010" and bc.next_receipt_no("SS", "garbage") == "SS-000001"
def test_receipt_email_has_text_and_html():
    subj, text, html = bc.receipt_email(_pay()); assert "SS-000007" in subj and "99.00" in text and "<html" in html
