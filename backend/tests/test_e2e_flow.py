"""End-to-end journey through the real API (SQLite, mocked external services): spec section 18."""
import os
from tests.test_core import c, tok
from app import paypal

def test_full_user_journey():
    h = tok("e2e@x.com")                                                         # 1-2 register + login
    parsed = c.post("/api/searches/parse", headers=h, json={"text": "דירת 3 חדרים בחולון עד 5,500 ש\"ח ללא תיווך"}).json()["params"]
    sid = c.post("/api/searches", headers=h, json={"name": parsed["name"], "category": parsed["category"], "location": parsed["location"], "max_price": parsed["max_price"]}).json()["id"]  # 3 create search
    r = c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח"}).json()  # 4-5 process + score
    assert r["status"] == "new" and r["score"] >= 60 and r["detail"]["factors"]
    assert any(x["id"] == r["id"] for x in c.get("/api/listings", headers=h).json())      # 6 display
    assert c.post(f"/api/listings/{r['id']}/save", headers=h).json()["status"] == "saved"  # 7 save
    assert c.get("/api/notifications", headers=h).json()["unread"] >= 1                    # 8 notification
    os.environ.update(PAYPAL_CLIENT_ID="i", PAYPAL_SECRET="s", PAYPAL_PLAN_PRO="P-PRO", PAYPAL_PLAN_VIP="P-VIP")
    paypal.create_subscription = lambda *a, **k: ("I-SUB1", "https://paypal.example/approve")
    uid = c.get("/api/auth/me", headers=h).json()["id"]
    assert c.post("/api/billing/checkout", headers=h, json={"plan": "pro"}).json()["approve_url"]  # 9 checkout
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter"       # not active before webhook
    paypal.verify_webhook = lambda headers, ev: True                                       # 10 verified webhook (mocked verifier)
    ev = {"id": "WH-E2E", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": "I-SUB1", "custom_id": uid, "plan_id": "P-PRO"}}
    assert c.post("/api/webhooks/paypal", json=ev).status_code == 200
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "pro"           # 11 activated
    os.environ["SUPER_ADMIN_EMAILS"] = "root-e2e@x.com"; boss = tok("root-e2e@x.com")
    ov = c.get("/api/admin/overview", headers=boss).json()                                 # 12 admin review
    assert ov["active_subscriptions"] >= 1 and ov["mrr_ils"] >= 99
