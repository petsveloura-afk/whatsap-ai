import os
os.environ["JWT_SECRET"] = "x" * 40
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["AUTO_CREATE_TABLES"] = "1"
if os.path.exists("test.db"): os.remove("test.db")
from fastapi.testclient import TestClient
from app.main import app
from app.extract import extract
c = TestClient(app)
def tok(email):
    c.post("/api/auth/register", json={"email": email, "password": "correct-horse-1"})
    r = c.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}
def test_extract_hebrew():
    e = extract("דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח.")
    assert e["rooms"] == 3 and e["location"] == "Holon" and e["price"] == 5200 and e["broker"] is False and e["condition"] == "renovated"
def test_auth_required():
    assert c.get("/api/searches").status_code == 401
def test_flow_and_isolation():
    a, b = tok("a@x.com"), tok("b@x.com")
    sid = c.post("/api/searches", headers=a, json={"name": "s", "category": "real_estate", "location": "Holon", "max_price": 5500}).json()["id"]
    txt = "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח."
    r = c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": txt})
    assert r.status_code == 201 and r.json()["status"] == "new" and r.json()["score"] >= 60
    assert c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": txt}).status_code == 409
    bad = c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": "דירה בחולון 9,000 ש״ח"}).json()
    assert bad["status"] == "rejected"
    assert c.get("/api/listings", headers=b).json() == []
    assert c.post("/api/listings/ingest", headers=b, json={"search_id": sid, "text": txt}).status_code == 404
    c.post(f"/api/searches/{sid}/pause", headers=a)
    assert c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": "דירה אחרת בחולון 5000 ש״ח"}).status_code == 409
def test_actions_admin_export_delete():
    os.environ["SUPER_ADMIN_EMAILS"] = "root@x.com"
    root, u = tok("root@x.com"), tok("u@x.com")
    sid = c.post("/api/searches", headers=u, json={"name": "s", "category": "real_estate"}).json()["id"]
    lid = c.post("/api/listings/ingest", headers=u, json={"search_id": sid, "text": "דירת 3 חדרים בחולון 5000 ש״ח"}).json()["id"]
    assert c.post(f"/api/listings/{lid}/save", headers=u).json()["status"] == "saved"
    assert c.post(f"/api/listings/{lid}/feedback", headers=u, json={"rating": 5, "note": "n"}).status_code == 200
    assert c.patch(f"/api/searches/{sid}", headers=u, json={"max_price": 6000}).status_code == 200
    assert c.get("/api/admin/users", headers=u).status_code == 403
    users = c.get("/api/admin/users", headers=root).json()
    uid = next(x["id"] for x in users if x["email"] == "u@x.com")
    assert c.patch(f"/api/admin/users/{uid}", headers=root, json={"is_active": False}).status_code == 200
    assert c.get("/api/auth/me", headers=u).status_code == 401
    assert any(l["action"] == "admin.user.patch" for l in c.get("/api/admin/audit-logs", headers=root).json())
    c.patch(f"/api/admin/users/{uid}", headers=root, json={"is_active": True})
    assert len(c.get("/api/me/export", headers=u).json()["listings"]) == 1
    assert c.delete("/api/me", headers=u).status_code == 204
    assert c.get("/api/auth/me", headers=u).status_code == 401
def test_telegram_ws_overview_agents():
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "s3cret"
    h = tok("tg@x.com"); token = h["Authorization"].split()[1]
    sid = c.post("/api/searches", headers=h, json={"name": "t", "category": "real_estate", "location": "Holon", "max_price": 5500}).json()["id"]
    src = c.post("/api/integrations/telegram/sources", headers=h, json={"search_id": sid}).json()
    H = {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}
    def upd(t): return {"message": {"text": t, "chat": {"id": 777}}}
    assert c.post("/api/integrations/telegram/webhook", json=upd("x")).status_code == 403
    assert c.post("/api/integrations/telegram/webhook", headers=H, json=upd("דירת 3 חדרים בחולון 5000 ש״ח")).json()["processed"] == 0
    assert c.post("/api/integrations/telegram/webhook", headers=H, json=upd(src["link_command"])).json()["linked"] is True
    with c.websocket_connect(f"/ws?token={token}") as w:
        assert c.post("/api/integrations/telegram/webhook", headers=H, json=upd("דירת 3 חדרים בחולון, משופצת, 5,000 ש״ח")).json()["processed"] == 1
        ev = w.receive_json()
        assert ev["type"] == "listing.discovered" and ev["correlation_id"]
    assert c.get("/api/dashboard/overview", headers=h).json()["total_listings"] == 1
    assert next(a for a in c.get("/api/agents", headers=h).json() if a["name"] == "matching")["processed"] >= 1
    try:
        with c.websocket_connect("/ws?token=bad") as w2: w2.receive_json()
        assert False
    except Exception: pass
def test_refresh_reset():
    from app import mail
    c.post("/api/auth/register", json={"email": "r@x.com", "password": "correct-horse-1"})
    r = c.post("/api/auth/login", json={"email": "r@x.com", "password": "correct-horse-1"}).json()
    r2 = c.post("/api/auth/refresh", json={"refresh_token": r["refresh_token"]})
    assert r2.status_code == 200
    assert c.post("/api/auth/refresh", json={"refresh_token": r["refresh_token"]}).status_code == 401
    assert c.post("/api/auth/refresh", json={"refresh_token": r2.json()["refresh_token"]}).status_code == 401
    sent = {}; mail.send_mail = lambda to, s, b: sent.update(b=b)
    assert c.post("/api/auth/forgot-password", json={"email": "r@x.com"}).status_code == 202
    tk = sent["b"].split("token=")[1]
    assert c.post("/api/auth/reset-password", json={"token": tk, "password": "new-password-123"}).status_code == 200
    assert c.post("/api/auth/reset-password", json={"token": tk, "password": "new-password-456"}).status_code == 400
    assert c.post("/api/auth/login", json={"email": "r@x.com", "password": "new-password-123"}).status_code == 200
def test_billing_whatsapp_metrics():
    from app import paypal, whatsapp
    os.environ["SUPER_ADMIN_EMAILS"] = "root@x.com"
    h = tok("bill@x.com"); uid = c.get("/api/auth/me", headers=h).json()["id"]
    assert c.post("/api/billing/checkout", headers=h, json={"plan": "pro"}).status_code == 503
    os.environ["PAYPAL_PLAN_PRO"] = "P-PRO"
    ev = {"id": "WH-1", "event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": "I-1", "custom_id": uid, "plan_id": "P-PRO"}}
    paypal.verify_webhook = lambda hd, e: False
    assert c.post("/api/webhooks/paypal", json=ev).status_code == 400
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter"
    paypal.verify_webhook = lambda hd, e: True
    assert c.post("/api/webhooks/paypal", json=ev).status_code == 200
    assert c.post("/api/webhooks/paypal", json=ev).json().get("duplicate")
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "pro"
    c.post("/api/webhooks/paypal", json=dict(ev, id="WH-2", event_type="BILLING.SUBSCRIPTION.CANCELLED"))
    assert c.get("/api/billing/subscription", headers=h).json()["plan"] == "starter"
    os.environ.update(WHATSAPP_TOKEN="t", WHATSAPP_PHONE_ID="1")
    got = []; whatsapp.notify = lambda to, text: got.append(to)
    assert c.put("/api/integrations/whatsapp/consent", headers=h, json={"number": "+972501234567", "consent": True}).status_code == 200
    sid = c.post("/api/searches", headers=h, json={"name": "w", "category": "real_estate", "location": "Holon", "max_price": 5500}).json()["id"]
    c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,100 ש״ח"})
    assert got == ["972501234567"]
    assert c.get("/api/admin/metrics", headers=h).status_code == 403
    m = c.get("/api/admin/metrics", headers=tok("root@x.com")).json()
    assert m["requests"] > 0
