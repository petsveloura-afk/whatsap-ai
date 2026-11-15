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
