"""v3.15 payments through the real API (SQLite) with PayPal mocked: order -> capture -> receipt -> history -> refund -> expiry."""
import datetime as dt, os
import pytest
from tests.test_core import c, tok
from app import paypal
from app.db import SessionLocal
from app.models import Payment, Subscription


@pytest.fixture(autouse=True)
def fake_paypal(monkeypatch):
    for k, v in dict(PAYPAL_CLIENT_ID="cid", PAYPAL_SECRET="sec", PAYPAL_PLAN_PRO="P-PRO", PAYPAL_PLAN_VIP="P-VIP").items(): monkeypatch.setenv(k, v)   # undone after each test: other test files expect PayPal unconfigured
    st = {"n": 0, "amount_delta": "0", "decline": False, "orders": {}}
    def create_order(amount, currency, custom_id, invoice_id, description, request_id, card=False):
        st["n"] += 1; oid = f"ORDER{st['n']:04d}XYZ"; st["orders"][oid] = {"amount": amount, "currency": currency, "custom_id": custom_id}; return oid
    def capture_order(order_id, request_id):
        if st["decline"]: raise paypal.PayPalError(422, "INSTRUMENT_DECLINED", "declined", "dbg")
        o = st["orders"][order_id]
        from decimal import Decimal
        val = str(Decimal(o["amount"]) + Decimal(st["amount_delta"]))
        return {"id": order_id, "status": "COMPLETED", "payer": {"email_address": "payer@x.com"}, "payment_source": {"card": {"brand": "VISA", "last_digits": "4242"}},
                "purchase_units": [{"custom_id": o["custom_id"], "payments": {"captures": [{"id": "CAP" + order_id, "status": "COMPLETED", "amount": {"value": val, "currency_code": o["currency"]}}]}}]}
    monkeypatch.setattr(paypal, "create_order", create_order); monkeypatch.setattr(paypal, "capture_order", capture_order)
    monkeypatch.setattr(paypal, "refund_capture", lambda *a, **k: {"id": "REF1", "status": "COMPLETED"})
    monkeypatch.setattr(paypal, "verify_webhook", lambda h, e: True)
    return st


def _pay(h, plan="pro", period="monthly", method="card"):
    r = c.post("/api/billing/order", headers=h, json={"plan": plan, "period": period, "method": method}); assert r.status_code == 200, r.text
    return r.json()


def test_config_requires_login_and_hides_secret():
    assert c.get("/api/billing/config").status_code == 401
    h = tok("bcfg@x.com"); j = c.get("/api/billing/config", headers=h).json()
    assert j["cards"] is True and j["paypal"]["client_id"] == "cid" and "sec" not in str(j) and {p["id"] for p in j["plans"]} == {"pro", "vip"}


def test_card_payment_full_flow_and_receipt():
    h = tok("bflow@x.com"); o = _pay(h)
    assert o["amount"] == "99.00" and o["currency"] == "ILS"
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter"          # nothing is granted before capture
    r = c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h); assert r.status_code == 200, r.text
    j = r.json(); assert j["status"] == "completed" and j["plan"] == "pro" and j["payment"]["receipt_no"].startswith("SS-") and j["payment"]["card_last4"] == "4242"
    sub = c.get("/api/billing/subscription", headers=h).json(); assert sub["plan"] == "pro" and sub["period_end"] and sub["recurring"] is False
    again = c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h).json()          # retry is idempotent: same receipt, no second payment
    assert again["payment"]["receipt_no"] == j["payment"]["receipt_no"]
    items = c.get("/api/billing/payments", headers=h).json()["items"]; assert len(items) == 1 and items[0]["status"] == "completed"
    rc = c.get(f"/api/billing/receipt/{items[0]['id']}", headers=h).json(); assert j["payment"]["receipt_no"] in rc["html"] and "99.00" in rc["html"]
    assert any("התשלום התקבל" in n["title"] for n in c.get("/api/notifications", headers=h).json()["items"])


def test_client_cannot_choose_the_price():
    h = tok("bprice@x.com")
    r = c.post("/api/billing/order", headers=h, json={"plan": "pro", "period": "monthly", "method": "card", "amount": "0.01"}); assert r.status_code == 200 and r.json()["amount"] == "99.00"
    assert c.post("/api/billing/order", headers=h, json={"plan": "starter", "period": "monthly"}).status_code == 422
    assert c.post("/api/billing/order", headers=h, json={"plan": "pro", "period": "daily"}).status_code == 422


def test_underpaid_capture_is_not_activated(fake_paypal):
    h = tok("bunder@x.com"); o = _pay(h); fake_paypal["amount_delta"] = "-98.00"
    assert c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h).status_code == 409
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter"


def test_declined_card_then_retry_with_new_order(fake_paypal):
    h = tok("bdecl@x.com"); o = _pay(h); fake_paypal["decline"] = True
    r = c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h); assert r.status_code == 402 and "נדחה" in r.json()["detail"]
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter" and c.get("/api/billing/payments", headers=h).json()["items"] == []
    fake_paypal["decline"] = False; o2 = _pay(h)
    assert c.post(f"/api/billing/order/{o2['order_id']}/capture", headers=h).json()["status"] == "completed"


def test_cannot_capture_someone_elses_order_or_read_their_receipt():
    a, b = tok("bown@x.com"), tok("bother@x.com"); o = _pay(a)
    assert c.post(f"/api/billing/order/{o['order_id']}/capture", headers=b).status_code == 404
    c.post(f"/api/billing/order/{o['order_id']}/capture", headers=a); pid = c.get("/api/billing/payments", headers=a).json()["items"][0]["id"]
    assert c.get(f"/api/billing/receipt/{pid}", headers=b).status_code == 404
    assert c.post("/api/billing/order/../../x/capture", headers=a).status_code in (404, 405)


def test_renew_stacks_time_and_plan_switch_is_blocked():
    h = tok("brenew@x.com"); o = _pay(h); c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h)
    end1 = dt.datetime.fromisoformat(c.get("/api/billing/subscription", headers=h).json()["period_end"])
    assert c.post("/api/billing/order", headers=h, json={"plan": "vip", "period": "monthly", "method": "card"}).status_code == 409
    o2 = _pay(h); c.post(f"/api/billing/order/{o2['order_id']}/capture", headers=h)
    end2 = dt.datetime.fromisoformat(c.get("/api/billing/subscription", headers=h).json()["period_end"])
    assert (end2 - end1) == dt.timedelta(days=30)
    assert c.post("/api/billing/checkout", headers=h, json={"plan": "pro"}).status_code == 409   # legacy recurring checkout still refuses an active plan


def test_prepaid_access_expires_by_date():
    h = tok("bexp@x.com"); o = _pay(h, "vip", "yearly"); assert o["amount"] == "1490.00"
    c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h); assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "vip"
    uid = c.get("/api/auth/me", headers=h).json()["id"]
    with SessionLocal() as db:
        s = db.query(Subscription).filter_by(user_id=uid).one(); s.current_period_end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1); db.commit()
    j = c.get("/api/billing/subscription", headers=h).json(); assert j["plan"] == "starter" and j["expired"] is True
    assert c.post("/api/billing/order", headers=h, json={"plan": "pro", "period": "monthly", "method": "card"}).status_code == 200   # can buy again after expiry


def test_webhook_completes_refunds_and_is_idempotent(fake_paypal):
    h = tok("bwh@x.com"); o = _pay(h)     # browser never calls capture (closed the tab); PayPal tells us by webhook
    ev = {"id": "WH-CAP-1", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAPWH1", "custom_id": o["payment_id"], "amount": {"value": "99.00", "currency_code": "ILS"}}}
    assert c.post("/api/webhooks/paypal", json=ev).status_code == 200 and c.get("/api/billing/subscription", headers=h).json()["plan"] == "pro"
    assert c.post("/api/webhooks/paypal", json=ev).json().get("duplicate")
    c.post("/api/webhooks/paypal", json=dict(ev, id="WH-CAP-2"))                      # a different event id for the same capture: still one receipt
    assert len(c.get("/api/billing/payments", headers=h).json()["items"]) == 1
    bad = dict(ev, id="WH-CAP-3", resource=dict(ev["resource"], amount={"value": "1.00", "currency_code": "ILS"})); c.post("/api/webhooks/paypal", json=bad)
    rf = {"id": "WH-REF-1", "event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {"id": "REFX", "links": [{"rel": "up", "href": "https://api.paypal.com/v2/payments/captures/CAPWH1"}]}}
    assert c.post("/api/webhooks/paypal", json=rf).status_code == 200
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter" and c.get("/api/billing/payments", headers=h).json()["items"][0]["status"] == "refunded"


def test_admin_refund_and_list():
    os.environ["SUPER_ADMIN_EMAILS"] = "boss-bill@x.com"; boss = tok("boss-bill@x.com"); h = tok("bref@x.com"); o = _pay(h)
    c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h); pid = c.get("/api/billing/payments", headers=h).json()["items"][0]["id"]
    assert c.get("/api/admin/billing/payments", headers=h).status_code == 403 and c.post(f"/api/admin/billing/payments/{pid}/refund", headers=h, json={}).status_code == 403
    lst = c.get("/api/admin/billing/payments", headers=boss).json(); assert any(i["id"] == pid for i in lst["items"]) and float(lst["revenue_total"]) >= 99
    assert c.post(f"/api/admin/billing/payments/{pid}/refund", headers=boss, json={"note": "test"}).status_code == 200
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter"
    assert c.post(f"/api/admin/billing/payments/{pid}/refund", headers=boss, json={}).status_code == 409      # not refundable twice


def test_recurring_subscription_renewal_gets_a_receipt(monkeypatch):
    h = tok("bsale@x.com"); uid = c.get("/api/auth/me", headers=h).json()["id"]
    monkeypatch.setattr(paypal, "create_subscription", lambda *a, **k: ("I-SALE1", "https://paypal.example/approve"))
    c.post("/api/billing/checkout", headers=h, json={"plan": "pro"})
    c.post("/api/webhooks/paypal", json={"id": "WH-S1", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": "I-SALE1", "custom_id": uid, "plan_id": "P-PRO"}})
    sale = {"id": "WH-S2", "event_type": "PAYMENT.SALE.COMPLETED", "resource": {"id": "SALE1", "billing_agreement_id": "I-SALE1", "amount": {"total": "99.00", "currency": "ILS"}}}
    assert c.post("/api/webhooks/paypal", json=sale).status_code == 200
    it = c.get("/api/billing/payments", headers=h).json()["items"]; assert len(it) == 1 and it[0]["method"] == "subscription" and it[0]["receipt_no"]
    assert c.get("/api/billing/subscription", headers=h).json()["recurring"] is True


def test_cancel_prepaid_has_a_clear_answer():
    h = tok("bcan@x.com"); o = _pay(h); c.post(f"/api/billing/order/{o['order_id']}/capture", headers=h)
    r = c.post("/api/billing/cancel", headers=h); assert r.status_code == 409 and "Prepaid" in r.json()["detail"]
