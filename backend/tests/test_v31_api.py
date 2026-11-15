"""API tests for v3.1 (need installed backend deps; run in CI)."""
import os
from tests.test_core import c, tok
from app.db import SessionLocal
from app import jobqueue, routes_v2, routes_v3, scout, growth
from app.models import User
TXT = "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח."

def _search(h): return c.post("/api/searches", headers=h, json={"name": "s", "category": "real_estate", "location": "Holon", "max_price": 9000}).json()["id"]

def test_security_headers_and_request_id():
    r = c.get("/api/health"); assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY" and r.headers["x-request-id"]

def test_api_key_lifecycle_scopes_and_isolation():
    a, b = tok("k1@x.com"), tok("k2@x.com"); sid = _search(a)
    k = c.post("/api/keys", headers=a, json={"name": "zap", "scopes": ["read"]}).json(); assert k["key"].startswith("ssk_")
    assert c.post("/api/keys", headers=a, json={"name": "x", "scopes": ["root"]}).status_code == 422
    kh = {"X-API-Key": k["key"]}
    assert c.post("/api/public/v1/ingest", headers=kh, json={"search_id": sid, "text": TXT}).status_code == 403      # read-only key
    ik = c.post("/api/keys", headers=a, json={"name": "ing", "scopes": ["ingest", "read"]}).json()
    assert c.post("/api/public/v1/ingest", headers={"X-API-Key": ik["key"]}, json={"search_id": sid, "text": TXT}).status_code == 201
    assert len(c.get("/api/public/v1/listings", headers=kh).json()["items"]) == 1
    assert c.get("/api/public/v1/usage", headers=kh).json()["daily_quota"] >= 200
    assert c.get("/api/public/v1/listings", headers={"X-API-Key": "ssk_nope"}).status_code == 401
    assert "key_hash" not in str(c.get("/api/keys", headers=a).json())
    assert c.delete(f"/api/keys/{k['id']}", headers=b).status_code == 404
    assert c.delete(f"/api/keys/{k['id']}", headers=a).status_code == 204 and c.get("/api/public/v1/listings", headers=kh).status_code == 401

def test_webhook_ssrf_guard_delivery_and_signature(monkeypatch):
    a = tok("wh1@x.com")
    assert c.post("/api/hooks", headers=a, json={"url": "http://localhost/hook"}).status_code == 422
    monkeypatch.setattr(scout, "check_url", lambda url, resolver=None: url)
    assert c.post("/api/hooks", headers=a, json={"url": "http://example.com/h"}).status_code == 422                  # https only
    h = c.post("/api/hooks", headers=a, json={"url": "https://example.com/h"}).json(); assert h["secret"].startswith("whsec_")
    sent = {}
    class R: status_code = 200
    class Cl:
        def post(s, url, content, headers, **k): sent.update(url=url, body=content, sig=headers["X-Sniper-Signature"]); return R()
        def close(s): pass
    class J: payload = {"endpoint_id": h["id"], "listing_id": None}
    with SessionLocal() as db: routes_v3.handle_webhook(db, J(), Cl())
    assert growth.verify(h["secret"], sent["body"], sent["sig"])
    assert c.get(f"/api/hooks/{h['id']}/deliveries", headers=a).json()[0]["status"] == "ok"

def test_referrals():
    a, b = tok("r1@x.com"), tok("r2@x.com"); code = c.get("/api/referrals/me", headers=a).json()["code"]
    assert c.post("/api/referrals/claim", headers=a, json={"code": code}).status_code == 404       # own code
    assert c.post("/api/referrals/claim", headers=b, json={"code": code}).status_code == 200
    assert c.post("/api/referrals/claim", headers=b, json={"code": code}).status_code == 409       # once only
    assert c.get("/api/referrals/me", headers=a).json()["referred"] == 1

def test_share_link_is_sanitised_expiring_and_revocable():
    a = tok("sh1@x.com"); sid = _search(a); lid = c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": TXT + " טלפון 050-1234567"}).json()["id"]
    s = c.post(f"/api/listings/{lid}/share", headers=a).json(); v = c.get(s["path"]).json()
    assert v["price"] == 5200 and "050" not in str(v) and "raw_text" not in v and "user_id" not in v
    assert c.delete(f"/api/shares/{s['id']}", headers=a).status_code == 204 and c.get(s["path"]).status_code == 404

def test_market_insight_and_pool_optin():
    a = tok("m1@x.com"); sid = _search(a)
    texts = ["רחוב הרצל קומה 2 עם מרפסת שמש", "שכונת קריית שרת קרוב לים וחניה מקורה", "ליד הקניון מעלית ומחסן משופצת מטבח חדש", "רחוב סוקולוב קומת קרקע עם גינה פרטית", "בבניין חדש עם ממ״ד ומיזוג בכל החדרים", "דחוף מהבעלים בלי עמלה פנויה מיידית"]
    for t, p in zip(texts, (5000, 5200, 5400, 5600, 5800, 4000)):
        assert c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": f"דירת 3 חדרים בחולון {t} מחיר {p} ש״ח"}).status_code == 201
    items = c.get("/api/listings", headers=a).json(); cheapest = min(items, key=lambda l: l["extracted"]["price"])
    ins = c.get(f"/api/listings/{cheapest['id']}/insight", headers=a).json(); assert ins["verdict"] in ("good_deal", "suspicious_low")
    assert c.get("/api/market/stats?category=real_estate&location=Holon", headers=a).json()["enough_data"] is True
    assert c.put("/api/market/pool", headers=a, json={"enabled": True}).json()["enabled"] is True

def test_full_export_and_delete_account_purges_new_tables():
    a = tok("del1@x.com"); sid = _search(a); c.post("/api/keys", headers=a, json={"name": "k"}); c.get("/api/referrals/me", headers=a)
    ex = c.get("/api/me/export/full", headers=a).json(); assert ex["tables"]["api_keys"] and "key_hash" not in str(ex)
    assert c.delete("/api/me", headers=a).status_code == 204
    with SessionLocal() as db: assert db.query(User).filter(User.email == "del1@x.com").count() == 0

def test_admin_errors_and_growth_and_tick():
    os.environ["SUPER_ADMIN_EMAILS"] = "boss31@x.com"; boss = tok("boss31@x.com")
    from app import errtrack
    with SessionLocal() as db:
        try: 1 / 0
        except ZeroDivisionError as e: errtrack.capture(db, e, "test password=hunter2")
        assert set(routes_v3.tick(db)) == {"webhooks", "digest", "market", "housekeeping"}
    errs = c.get("/api/admin/errors", headers=boss).json(); assert errs and "hunter2" not in str(errs)
    assert "open_errors" in c.get("/api/admin/growth", headers=boss).json()
    assert c.get("/api/admin/errors", headers=tok("plain31@x.com")).status_code == 403

def test_new_source_kind_accepted_and_stale_job_recovery(monkeypatch):
    monkeypatch.setattr(scout, "check_url", lambda url, resolver=None: url)
    from app import scale
    from app.models2 import AgentJob, AgentEvent
    a = tok("src31@x.com"); sid = _search(a)
    assert c.post("/api/sources", headers=a, json={"search_id": sid, "kind": "jsonld", "url": "https://x.example/p"}).status_code == 201
    assert c.post("/api/sources", headers=a, json={"search_id": sid, "kind": "ftp", "url": "https://x.example/p"}).status_code == 422
    with SessionLocal() as db:
        j = jobqueue.enqueue(db, "poll_source", {"source_id": "none"}); j = scale.claim(db); assert j.status == "running"
        assert scale.recover_stale(db, lease_minutes=-1) >= 1 and db.get(AgentJob, j.id).status == "pending"
