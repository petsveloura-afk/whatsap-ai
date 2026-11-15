"""API tests for sources/queue/notifications/admin/flags. Require the installed backend deps (run in CI)."""
import os
from tests.test_core import c, tok
from app.db import SessionLocal
from app import jobqueue, routes_v2, scout
from app.models import User

FEED = '<rss><channel><item><title>דירת 3 חדרים בחולון</title><description>משופצת, ללא תיווך, 5,200 ש"ח</description><link>https://f.example/1</link><guid>1</guid></item><item><title>דירת 3 חדרים בחולון</title><description>משופצת, ללא תיווך, 5,200 ש"ח</description><guid>2</guid></item></channel></rss>'
class R:
    def __init__(s, text, code=200): s.text, s.status_code, s.headers, s.content = text, code, {}, text.encode()
    def raise_for_status(s): pass
class FakeClient:
    def get(s, url, **k): return R("", 404) if url.endswith("robots.txt") else R(FEED)
    def close(s): pass

def _admin():
    os.environ["SUPER_ADMIN_EMAILS"] = "boss@x.com"; return tok("boss@x.com")

def test_source_poll_queue_notification_and_isolation(monkeypatch):
    monkeypatch.setattr(scout, "check_url", lambda url, resolver=None: url)
    a, b = tok("v2a@x.com"), tok("v2b@x.com")
    sid = c.post("/api/searches", headers=a, json={"name": "s", "category": "real_estate", "location": "Holon", "max_price": 5500}).json()["id"]
    src = c.post("/api/sources", headers=a, json={"search_id": sid, "kind": "rss", "url": "https://f.example/feed"})
    assert src.status_code == 201
    srcid = src.json()["id"]
    assert c.get("/api/sources", headers=b).json() == []
    assert c.post(f"/api/sources/{srcid}/poll", headers=b).status_code == 404
    assert c.post(f"/api/sources/{srcid}/poll", headers=a).json()["queued"] is True
    assert c.post(f"/api/sources/{srcid}/poll", headers=a).json()["queued"] is False  # dedupe while active
    with SessionLocal() as db:
        assert jobqueue.run_once(db, {"poll_source": lambda d, j: routes_v2.handle_poll(d, j, client=FakeClient())}) is True
    ev = c.get(f"/api/sources/{srcid}/events", headers=a).json()
    assert ev[0]["status"] == "ok" and "new=1" in ev[0]["detail"]
    assert c.get("/api/sources", headers=a).json()[0]["status"] == "OK"
    n = c.get("/api/notifications", headers=a).json()
    assert n["unread"] >= 1 and c.get("/api/notifications", headers=b).json()["items"] == []

def test_failed_job_retries_then_dead_letter():
    with SessionLocal() as db:
        j = jobqueue.enqueue(db, "boom", {}, max_attempts=2); jid = j.id
        def boom(d, j): raise RuntimeError("x")
        for _ in range(2):
            from app.models2 import AgentJob
            jj = db.get(AgentJob, jid); jj.run_after = jobqueue._now(); db.commit()
            jobqueue.run_once(db, {"boom": boom})
        assert db.get(AgentJob, jid).status == "dead"

def test_flags_admin_only_and_capabilities():
    u = tok("plain@x.com"); boss = _admin()
    assert c.patch("/api/admin/system-settings", headers=u, json={"flags": {"llm_extraction": True}}).status_code == 403
    r = c.patch("/api/admin/system-settings", headers=boss, json={"flags": {"llm_extraction": True}})
    assert r.status_code == 200 and r.json()["flags"]["llm_extraction"] is True
    assert c.patch("/api/admin/system-settings", headers=boss, json={"flags": {"nope": True}}).status_code == 400
    c.patch("/api/admin/system-settings", headers=boss, json={"flags": {"llm_extraction": False}})
    assert c.get("/api/memory/similar?q=abc", headers=u).status_code == 503

def test_admin_overview_and_maintenance_mode():
    boss, u = _admin(), tok("plain2@x.com")
    assert c.get("/api/admin/overview", headers=u).status_code == 403
    assert "mrr_ils" in c.get("/api/admin/overview", headers=boss).json()
    c.patch("/api/admin/system-settings", headers=boss, json={"flags": {"maintenance_mode": True}})
    from app import flags
    with SessionLocal() as db: flags.load(db, True)
    assert c.post("/api/searches", headers=u, json={"name": "x", "category": "real_estate"}).status_code == 503
    c.patch("/api/admin/system-settings", headers=boss, json={"flags": {"maintenance_mode": False}})
