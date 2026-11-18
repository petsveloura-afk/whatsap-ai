"""Category registry: 42 new categories, original ones untouched, detection only fills gaps, API + scoring wiring."""
import pytest
from tests.test_core import c, tok
from app import categories as C
from app.extract import extract, detect_category
ORIGINAL = {"real_estate", "vehicles", "electronics", "furniture", "business", "services", "other"}
def test_counts_and_original_keys_kept():
    assert len(C.NEW_KEYS) >= 40 and len(C.CATS) == 49 and ORIGINAL <= set(C.CATS) and not (ORIGINAL & set(C.NEW_KEYS))
    for k in ORIGINAL: assert C.CATS[k]["builtin"] and len(C.CATS[k]["subs"]) >= 3
def test_every_category_is_complete():
    for k, v in C.CATS.items():
        assert v["label"] and v["group"] and v["icon"] and len(v["subs"]) >= 3 and len(v["attrs"]) >= 2, k
        if not v["builtin"]: assert len(v["strong"]) >= 5 and v["sites"], k
        for s in v["subs"]: assert s["key"] and s["label"], k
def test_registry_installed_into_existing_modules():
    from app import llm, feeds, discovery, scandeep, scanplus
    assert set(C.NEW_KEYS) <= llm.CATS
    for k in ("pets", "boats", "jobs"): assert k in feeds.CAT_HE
    assert "tickets" in discovery.SITES and "tickets" in scandeep.SITES and "tickets" in scanplus.SITE_PACK
@pytest.mark.parametrize("text,cat", [("מוכר גיטרה אקוסטית כמעט חדשה", "music_instruments"), ("למכירה סירת מנוע 90 כוחות סוס", "boats"), ("אופניים חשמליים בחצי מחיר", "bicycles"),
    ("דרוש מפתח פרילנס משרה חלקית", "jobs"), ("צימר רומנטי עם ג'קוזי לסוף שבוע", "vacation_rentals"), ("כרטיסים להופעה ביום שישי", "tickets"),
    ("לגו מארז חדש לילדים", "toys"), ("טרקטור חקלאי במצב מצוין", "industrial"), ("עסק למכירה בית קפה במרכז", "business_for_sale"), ("הליכון חשמלי ומשקולות", "fitness")])
def test_new_categories_detected(text, cat): assert extract(text)["category"] == cat and detect_category(text) == cat
@pytest.mark.parametrize("text,cat", [("דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח.", "real_estate"), ("אייפון 13 128GB במצב מצוין", "electronics"),
    ("יונדאי i10 2019 יד ראשונה 60,000 ק״מ", "vehicles"), ("ספה פינתית 3 מושבים", "furniture")])
def test_original_classifications_unchanged(text, cat): assert extract(text)["category"] == cat
def test_ambiguous_or_empty_text_stays_unclassified():
    assert C.detect_new("שלום מה שלומך")[0] is None and C.detect_new("")[0] is None
def test_sub_category_detection():
    assert C.detect_new("אופני הרים שלדה אלומיניום")[2] == "mtb" or C.detect_sub("bicycles", "אופני הרים") == "mtb"
def test_compatible_relations():
    assert C.compatible("smartphones", "electronics") and C.compatible("electronics", "smartphones") and C.compatible("gaming", "computers")
    assert not C.compatible("pets", "electronics") and not C.compatible(None, "pets")
def test_public_api():
    r = c.get("/api/categories").json(); assert r["count"] == 49 and r["groups"] and any(i["key"] == "pets" and i["subs"] for i in r["items"])
    assert len(c.get("/api/categories?full=false").json()["items"]) == 49
    assert c.get("/api/categories/boats").json()["label"] == "כלי שיט" and c.get("/api/categories/nope").status_code == 404
    d = c.post("/api/categories/detect", json={"text": "מחפש שותף, יש חדר פנוי להשכרה בתל אביב"}).json(); assert d["category"] == "roommates"
def test_nl_search_uses_new_categories():
    h = tok("catnl@x.com"); r = c.post("/api/searches/parse", headers=h, json={"text": "מחפש אופניים חשמליים בחיפה עד 4000 שקל"}).json()
    assert r["params"]["category"] == "bicycles" and r["params"]["max_price"] == 4000
def test_search_and_listing_flow_in_new_category():
    h = tok("catflow@x.com")
    sid = c.post("/api/searches", headers=h, json={"name": "גיטרה", "category": "music_instruments", "max_price": 2000}).json()["id"]
    r = c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": "גיטרה אקוסטית יאמאהה במצב מצוין, 900 ש״ח, תל אביב"}); assert r.status_code == 201, r.text
    assert r.json()["extracted"]["category"] == "music_instruments" and r.json()["score"] >= 60
def test_specialisation_counts_as_category_match():
    h = tok("catrel@x.com")
    sid = c.post("/api/searches", headers=h, json={"name": "אלקטרוניקה", "category": "electronics", "max_price": 6000}).json()["id"]
    r = c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": "פלייסטיישן 5 עם שני בקרים, 1,800 ש״ח, חיפה"}); assert r.status_code == 201
    assert r.json()["score"] >= 60 and "category" not in str(r.json()["detail"].get("rejection_reasons", []))
def test_wrong_category_still_rejected():
    h = tok("catbad@x.com")
    sid = c.post("/api/searches", headers=h, json={"name": "חיות", "category": "pets", "max_price": 3000}).json()["id"]
    r = c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": "מכונת כביסה 8 ק״ג כמעט חדשה, 900 ש״ח, חולון"}); assert r.status_code == 201 and r.json()["status"] == "rejected"
