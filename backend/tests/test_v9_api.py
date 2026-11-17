"""v3.16: profile, learned-memory sync, diagnostics, brain+ pure helpers. No network."""
import datetime as dt
from tests.test_core import c, tok
from app import brain_plus as BP
from app.db import SessionLocal
from app.models import User
from sqlalchemy import select

HOLON = "דירת 3 חדרים בחולון, קומה 2, חניה, מעלית, 5,200 ש״ח להשכרה"
HOLON2 = "דירת 4 חדרים בחולון, מרפסת, חניה, מעלית, 5,600 ש״ח להשכרה, קומה 3"


def _setup(email):
    h = tok(email)
    sid = c.post("/api/searches", headers=h, json={"name": "v9", "category": "real_estate", "location": "Holon", "max_price": 7000}).json()["id"]
    ids = [c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": t}).json()["id"] for t in (HOLON, HOLON2)]
    return h, sid, ids


def test_profile_empty_then_rich_and_isolated():
    h = tok("v9empty@x.com")
    p = c.get("/api/profile", headers=h).json()
    assert p["user"]["initials"] and p["stats"]["listings"] == 0 and p["plan"]["id"] == "starter"
    assert p["completeness"]["score"] < 60 and p["completeness"]["tips"]
    h2, sid, ids = _setup("v9rich@x.com")
    for i in ids: assert c.post(f"/api/listings/{i}/save", headers=h2).status_code == 200
    p2 = c.get("/api/profile", headers=h2).json()
    assert p2["stats"]["listings"] == 2 and p2["stats"]["saved"] == 2 and p2["plan"]["searches_used"] == 1
    assert p2["insights"]["positive"] == 2 and p2["insights"]["statements"]
    assert c.get("/api/profile", headers=h).json()["stats"]["listings"] == 0     # per-user isolation
    assert c.get("/api/profile").status_code in (401, 403)                         # auth required


def test_sync_memory_is_idempotent_and_honours_privacy():
    h, sid, ids = _setup("v9sync@x.com")
    r0 = c.post("/api/profile/sync-memory", headers=h).json()
    assert r0["added"] == 0 and "מספיק" in r0["message"]                           # no evidence -> nothing invented
    for i in ids: c.post(f"/api/listings/{i}/save", headers=h)
    r1 = c.post("/api/profile/sync-memory", headers=h).json()
    assert r1["added"] >= 1 and all(s.startswith(BP.LEARNED_PREFIX) for s in r1["statements"])
    r2 = c.post("/api/profile/sync-memory", headers=h).json()
    assert r2["added"] == 0 and r2["known"] >= 1                                   # pressing twice never duplicates
    mem = c.get("/api/agent/memory", headers=h).json()["items"]
    assert len([m for m in mem if m["text"].startswith(BP.LEARNED_PREFIX)]) == r1["added"]
    assert c.get("/api/profile", headers=h).json()["memory"]["learned"] == r1["added"]
    c.put("/api/memory/preferences", headers=h, json={"personalization_enabled": False})
    assert c.post("/api/profile/sync-memory", headers=h).status_code == 409


def test_diagnostics_staff_only():
    h = tok("v9plain@x.com")
    assert c.get("/api/admin/diagnostics", headers=h).status_code == 403
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "v9plain@x.com")); u.role = "admin"; db.commit()
    d = c.get("/api/admin/diagnostics", headers=h).json()
    names = {x["name"]: x for x in d["checks"]}
    assert {"database", "tables", "migrations", "routes", "agent_memory", "queue", "brains", "flags"} <= set(names)
    assert names["database"]["ok"] and names["tables"]["ok"] and names["routes"]["ok"], d


def test_brain_plus_pure():
    ins = BP.insights([{"status": "saved", "score": 80, "extracted": {"location": "Holon", "category": "real_estate", "rooms": 3, "price": 5000, "features": ["parking"], "deal_type": "rent"}},
                       {"status": "saved", "score": 90, "extracted": {"location": "Holon", "category": "real_estate", "rooms": 4, "price": 6000, "features": ["parking", "elevator"], "deal_type": "rent"}},
                       {"status": "rejected", "score": 40, "extracted": {"location": "Bat Yam"}}, {"status": "rejected", "score": 30, "extracted": {"location": "Bat Yam"}}])
    assert ins["positive"] == 2 and ins["negative"] == 2 and ins["confidence"] == "low" and ins["avoid_cities"] == ["Bat Yam"]
    st = BP.memory_statements(ins); assert any("חולון" in s for s in st) and any("חניה" in s for s in st) and all(len(s) <= 200 for s in st)
    assert BP.memory_statements(BP.insights([{"status": "saved", "extracted": {"location": "Holon"}}])) == []   # one listing is not a taste
    assert BP.completeness({"searches": 1, "listings": 1, "saved": 3, "memories": 2, "personalization": True, "telegram": True})["score"] == 100
    now = dt.datetime.now(dt.timezone.utc)
    assert BP.recency_boost(now, now) > BP.recency_boost(now - dt.timedelta(days=200), now) > 0 and BP.recency_boost(None) == 0.0
    assert BP.recency_boost(dt.datetime.now(), None) >= 0                           # naive datetimes (SQLite) never raise
    assert BP.initials("dana.levi@x.com") == "DL" and BP.initials("") == "?"


def test_whatsapp_consent_masked_and_revocable():
    h = tok("v9wa@x.com")
    assert c.get("/api/profile", headers=h).json()["contact"]["whatsapp_masked"] is None
    assert c.put("/api/integrations/whatsapp/consent", headers=h, json={"number": "+972501234567", "consent": True}).status_code == 200
    ct = c.get("/api/profile", headers=h).json()["contact"]
    assert ct["whatsapp_consent"] is True and ct["whatsapp_masked"] == "•••• 4567" and "972501234567" not in str(ct)
    assert c.delete("/api/integrations/whatsapp/consent", headers=h).json() == {"consent": False}
    assert c.delete("/api/integrations/whatsapp/consent", headers=h).status_code == 200            # idempotent
    ct = c.get("/api/profile", headers=h).json()["contact"]
    assert ct["whatsapp_consent"] is False and ct["whatsapp_masked"] == "•••• 4567"                 # number kept for re-enable
    assert c.get("/api/integrations/whatsapp/status", headers=h).json()["consent"] is False
    assert c.delete("/api/integrations/whatsapp/consent").status_code in (401, 403)
