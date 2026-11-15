from tests.test_core import c, tok
def test_memory_flow_and_isolation():
    a, b = tok("m1@x.com"), tok("m2@x.com")
    sid = c.post("/api/searches", headers=a, json={"name": "m", "category": "real_estate", "location": "Holon", "max_price": 5500}).json()["id"]
    lid = c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": "דירת 4 חדרים בחולון, משופצת, 5,000 ש״ח, ליד הים"}).json()["id"]
    assert c.post(f"/api/listings/{lid}/save", headers=a).status_code == 200
    assert len(c.get("/api/memory", headers=a).json()["items"]) == 1
    assert c.get("/api/memory", headers=b).json()["items"] == []
    assert c.put("/api/memory/preferences", headers=a, json={"personalization_enabled": False}).json()["personalization_enabled"] is False
    assert len(c.get("/api/me/export", headers=a).json()["memory"]) == 1
    assert c.delete("/api/memory", headers=a).status_code == 204
    assert c.get("/api/memory", headers=a).json()["items"] == []
