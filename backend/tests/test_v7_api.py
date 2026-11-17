"""API tests for v3.13 pro toolkit (need installed backend deps; run in CI). Network and AI are replaced by fakes."""
import os
from tests.test_core import c, tok
from app import discovery, routes_v7, brains
from app.db import SessionLocal
from app.models import User
TXT = "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח. מעלית וחניה. לתיאום 050-1234567"


def _search(h, **kw): return c.post("/api/searches", headers=h, json={"name": "s", "category": "real_estate", "location": "Holon", "max_price": 9000, **kw}).json()["id"]
def _lid(h, text=TXT):
    sid = _search(h); return sid, c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": text}).json()["id"]


def test_catalog_gate_and_trial(monkeypatch):
    monkeypatch.delenv("PRO_OPEN", raising=False); h = tok("pro1@x.com")
    cat = c.get("/api/pro/catalog", headers=h).json(); assert cat["plan"] == "starter" and len(cat["features"]) >= 30 and any(f["id"] == "mortgage" and f["allowed"] for f in cat["features"])
    assert c.post("/api/pro/calc/mortgage", headers=h, json={"price": 2000000, "ltv_pct": 70}).json()["loan"] == 1400000
    assert c.post("/api/pro/calc/purchase-costs", headers=h, json={"price": 2500000}).json()["items"][0]["amount"] == 20538
    assert c.post("/api/pro/calc/mortgage", headers=h, json={"price": -5}).status_code == 422
    for _ in range(5): assert c.post("/api/pro/calc/yield", headers=h, json={"price": 2000000, "monthly_rent": 6000}).status_code == 200    # trial of 5
    r = c.post("/api/pro/calc/yield", headers=h, json={"price": 2000000, "monthly_rent": 6000}); assert r.status_code == 402 and "Pro" in r.json()["detail"]
    assert c.get("/api/pro/catalog", headers=h).json()["features"][0]["id"] and c.get("/api/pro/catalog").status_code == 401
    monkeypatch.setenv("PRO_OPEN", "1"); assert c.post("/api/pro/calc/yield", headers=h, json={"price": 2000000, "monthly_rent": 6000}).status_code == 200


def test_listing_tools_and_isolation(monkeypatch):
    monkeypatch.setenv("PRO_OPEN", "1"); a, b = tok("pro2@x.com"), tok("pro3@x.com"); sid, lid = _lid(a)
    assert any(t["code"] == "elevator" for t in c.get(f"/api/pro/listings/{lid}/tags", headers=a).json()["tags"])
    assert c.get(f"/api/pro/listings/{lid}/fraud", headers=a).json()["level"] == "low" and len(c.get(f"/api/pro/listings/{lid}/checklist", headers=a).json()["groups"]) == 3
    n = c.get(f"/api/pro/listings/{lid}/negotiation?lang=en", headers=a).json(); assert n["enough"] and n["open"] < n["target"] and n["lang"] == "en"
    assert "5,200" in c.get(f"/api/pro/listings/{lid}/share-pack", headers=a).json()["whatsapp"]
    sh = c.get(f"/api/pro/listings/{lid}/sheet", headers=a).json(); assert sh["mime"] == "text/html" and 'dir="rtl"' in sh["content"]
    ai = c.post(f"/api/pro/listings/{lid}/ai", headers=a, json={"action": "analyze"}).json(); assert ai["engine"] == "rules" and ai["pros"]            # AI flag is off by default: rule-based answer
    for p in ("fraud", "tags", "checklist", "negotiation", "share-pack", "sheet", "fair-price"): assert c.get(f"/api/pro/listings/{lid}/{p}", headers=b).status_code == 404
    lid2 = c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": "דירת 3 חדרים בחולון, 5,900 ש״ח, קומה 4 עם מרפסת וחניה. 052-7654321"}).json()["id"]
    cmp_ = c.post("/api/pro/compare", headers=a, json={"ids": [lid, lid2]}).json(); assert cmp_["winner"] in (lid, lid2) and len(cmp_["ranking"]) == 2
    assert c.post("/api/pro/compare", headers=a, json={"ids": [lid, lid]}).status_code == 422            # the same listing twice is not a comparison
    assert c.post("/api/pro/compare", headers=b, json={"ids": [lid, lid2]}).status_code == 404


def test_crm_reminders_rules_clients(monkeypatch):
    monkeypatch.setenv("PRO_OPEN", "1"); h = tok("pro4@x.com"); sid, lid = _lid(h)
    r = c.put(f"/api/pro/crm/{lid}", headers=h, json={"stage": "contacted", "note": "דיברתי עם המוכר", "due": "2020-01-01"}).json(); assert r["stage"] == "contacted"
    assert c.put(f"/api/pro/crm/{lid}", headers=h, json={"stage": "weird"}).status_code == 422
    board = c.get("/api/pro/crm", headers=h).json(); assert board["tracked"] == 1 and any(s["id"] == "contacted" and len(s["items"]) == 1 for s in board["stages"])
    assert c.get("/api/pro/reminders", headers=h).json()["items"][0]["overdue"] is True
    with SessionLocal() as db: assert routes_v7.reminders_tick(db) == 1                                    # overdue reminder becomes an in-app notification once
    with SessionLocal() as db: assert routes_v7.reminders_tick(db) == 0
    rules = c.put("/api/pro/rules", headers=h, json={"rules": [{"name": "חולון", "city": "holon", "max_price": 6000}]}).json()["rules"]; assert rules[0]["id"]
    assert c.post("/api/pro/rules/test", headers=h, json={"rule": rules[0]}).json()["matches"] == 1
    assert c.put("/api/pro/rules", headers=h, json={"rules": [{"min_price": 9, "max_price": 1}]}).status_code == 422
    cl = c.put("/api/pro/clients", headers=h, json={"clients": [{"name": "דנה", "budget_max": 6000, "cities": ["Holon"]}]}).json()["clients"][0]
    m = c.get(f"/api/pro/clients/{cl['id']}/matches", headers=h).json(); assert m["matches"] and m["matches"][0]["fit"] >= 50 and m["matches"][0]["message"]
    assert c.get("/api/pro/clients/nope/matches", headers=h).status_code == 404


def test_reports_export_paste_brand(monkeypatch):
    monkeypatch.setenv("PRO_OPEN", "1"); h = tok("pro5@x.com"); sid, lid = _lid(h)
    csv = c.get("/api/pro/export/csv", headers=h).json(); assert csv["rows"] == 1 and csv["content"].startswith("\ufeff")
    assert c.get("/api/pro/report/market?category=real_estate", headers=h).json()["n"] == 1 and c.get("/api/pro/report/weekly", headers=h).json()["count"] == 1
    t = c.post("/api/pro/templates", headers=h, json={"listing_id": lid, "kind": "first", "lang": "ru"}).json(); assert "Holon" in t["text"] or "Здравствуйте" in t["text"]
    assert c.put("/api/pro/settings", headers=h, json={"name": "Dana Homes", "phone": "050-1234567", "color": "#ff0000"}).json()["brand"]["name"] == "Dana Homes"
    p = c.post("/api/pro/paste/clean", headers=h, json={"text": "[16/11/2026, 10:01] דנה: דירה 4 חדרים בחולון 6000 ש\"ח\n[16/11/2026, 10:02] יוסי: רכב מאזדה 3 שנת 2018 60000 ש\"ח"}).json(); assert p["found"] == 2
    assert c.get("/api/pro/clusters", headers=h).json()["scanned"] == 1


def test_scan_plus_plan_and_run(monkeypatch):
    monkeypatch.setenv("PRO_OPEN", "1"); monkeypatch.setenv("TAVILY_API_KEY", "t1"); h = tok("pro6@x.com"); sid = _search(h, required_keywords=["3"])
    pl = c.post("/api/pro/scan/plus", headers=h, json={"search_id": sid, "plan_only": True, "queries": 5}).json(); assert len(pl["plan"]) == 5 and pl["plan"][0]["site"] is None
    calls = []
    def fake(q, n, site=None): calls.append((q, site)); return [{"title": "דירת 3 חדרים בחולון", "url": f"https://www.yad2.co.il/item/{len(calls)}", "snippet": "דירת 3 חדרים בחולון, 5,200 ש\"ח, חניה ומעלית, 050-1234567 ליצירת קשר"}] if len(calls) < 3 else []
    monkeypatch.setattr(discovery, "search", fake); r = c.post("/api/pro/scan/plus", headers=h, json={"search_id": sid, "queries": 4}).json()
    assert len(calls) == 4 and r["found"] == 2 and r["new"] + r["rejected"] + r["duplicates"] >= 1 and "headline" in r["summary"]
    assert c.get("/api/pro/scan/report", headers=h).json()["engines"]
    assert c.put("/api/pro/scan/auto", headers=h, json={"enabled": True, "hours": 12, "search_ids": [sid]}).json()["enabled"] is True


def test_autoscan_alerts_and_admin(monkeypatch):
    monkeypatch.setenv("PRO_OPEN", "1"); monkeypatch.setenv("TAVILY_API_KEY", "t1"); h = tok("pro7@x.com"); sid, lid = _lid(h)
    c.put("/api/pro/scan/auto", headers=h, json={"enabled": True, "hours": 6, "search_ids": [sid], "queries": 2})
    c.put("/api/pro/rules", headers=h, json={"rules": [{"name": "הכול", "min_score": 1}]})
    monkeypatch.setattr(discovery, "search", lambda q, n, site=None: [])
    with SessionLocal() as db:
        assert routes_v7.autoscan_tick(db) >= 1
        assert routes_v7.alerts_tick(db) >= 0
    assert c.get("/api/pro/scan/auto", headers=h).json()["log"]
    assert c.get("/api/admin/pro/overview", headers=h).status_code == 403
