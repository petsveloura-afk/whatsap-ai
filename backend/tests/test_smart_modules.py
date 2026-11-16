"""Pure-module tests for the upgraded extraction / scoring / NL search (no DB, no network)."""
from types import SimpleNamespace as N
from app.extract import extract, find_cities, canon_city, find_price
from app.scoring import score, risks
from app.nlsearch import parse_search

def cfg(**kw):
    d = dict(category="real_estate", location="Holon", max_price=5500, min_price=None, weights=None, required_keywords=[], excluded_keywords=[])
    d.update(kw); return N(**d)

def test_original_contract_kept():
    e = extract("דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח.")
    assert (e["rooms"], e["location"], e["price"], e["broker"], e["condition"], e["currency"]) == (3, "Holon", 5200, False, "renovated", "ILS")
    assert 0 <= e["confidence"] <= 1

def test_more_cities_and_prefixes():
    assert find_cities("בחולון או בת ים") == ["Holon", "Bat Yam"]
    assert find_cities("דירה בקריית גת ובבאר שבע") == ["Kiryat Gat", "Beer Sheva"]
    assert canon_city("חולון") == canon_city("holon") == "Holon"
    assert find_cities("ארנונה גבוהה") == []          # no false city inside other words

def test_price_formats():
    assert find_price("2.4 מיליון ₪")[0] == 2_400_000
    assert find_price("₪ 5,200")[0] == 5200
    assert find_price("5.200 ש\"ח")[0] == 5200            # Israeli thousands dot
    assert find_price("68 אלף ש\"ח")[0] == 68000
    assert find_price("ארנונה 400 ש\"ח, שכירות 7,500 ש\"ח")[0] == 7500   # fees are not the price
    assert find_price("1,500 $")[1] == "USD"

def test_vehicle_and_phone():
    v = extract("טויוטה קורולה שנת 2019 יד שנייה 85 אלף ק\"מ 68,000 ש\"ח")
    assert (v["category"], v["brand"], v["year"], v["km"], v["hand"]) == ("vehicles", "Toyota", 2019, 85000, 2)
    p = extract("iPhone 13 pro 256GB 1800 ₪")
    assert (p["category"], p["brand"], p["storage_gb"]) == ("electronics", "Apple", 256)

def test_no_substring_false_positives():
    e = extract("שלושה וחצי חדרים בתל אביב ארנונה 400 ש\"ח 7,500 ש\"ח")
    assert e["category"] == "real_estate" and e["rooms"] == 3.5 and e["brand"] is None and e["price"] == 7500

def test_scam_flags_become_risks():
    e = extract("תעביר מקדמה לפני צפייה בדירה בחולון 1000 ש\"ח")
    assert any("advance payment" in r for r in risks(e, cfg()))

def test_negated_broker_is_not_excluded():
    t = "דירת 3 חדרים בחולון ללא תיווך 5,000 ש\"ח"
    r = score(extract(t), cfg(excluded_keywords=["תיווך"]), t)
    assert not r["rejection_reasons"] and r["score"] >= 60
    t2 = "דירת 3 חדרים בחולון 5,000 ש\"ח תיווך אנגלו סכסון"
    assert score(extract(t2), cfg(excluded_keywords=["תיווך"]), t2)["rejection_reasons"]

def test_numeric_keyword_is_rooms_not_price_digits():
    t = "דירת 4 חדרים בחולון 3,500 ש\"ח"
    assert score(extract(t), cfg(required_keywords=["3"]), t)["factors"]["preference"] == 0.0
    assert score(extract(t), cfg(required_keywords=["4"]), t)["factors"]["preference"] == 1.0

def test_hebrew_location_in_search_config():
    t = "דירה בחולון 5000 ש\"ח"
    assert score(extract(t), cfg(location="חולון"), t)["factors"]["location"] == 1.0

def test_nl_search_upgrades():
    r = parse_search("דירה בתל אביב בין 6000 ל-8000 עם חניה ומעלית")["params"]
    assert (r["min_price"], r["max_price"]) == (6000, 8000) and {"חניה", "מעלית"} <= set(r["required_keywords"])
    assert parse_search("רכב טויוטה עד 70 אלף ש\"ח")["params"]["max_price"] == 70000
    assert parse_search("apartment Herzliya up to 3.5 million")["params"]["max_price"] == 3_500_000
    assert parse_search("iphone 13 מתחת 2000 ₪")["params"]["max_price"] == 2000
    assert parse_search("something nice")["clarifications"] and len(parse_search("something nice")["clarifications"]) == 2

# ---- v3.2 pure modules: assistant, feeds, llm presets ----
def _rows():
    mk = lambda i, sc, st, city, price, **k: {"id": i, "score": sc, "status": st, "risks": k.pop("risks", []), "detail": k.pop("detail", {}), "extracted": {"location": city, "price": price, "rooms": 3.0, "currency": "ILS", **k}}
    return [mk("a", 90, "new", "Holon", 5200, broker=False), mk("b", 70, "new", "Holon", 4800), mk("c", 80, "new", "Bat Yam", 4500, risks=["x"]),
            mk("d", 30, "rejected", "Holon", 9000, detail={"rejection_reasons": ["price outside range"]})]

def test_assistant_intents():
    from app.assistant import answer, report, explain
    r = _rows()
    assert answer("מה הכי זול?", r)["listing_ids"][0] == "c"
    assert answer("מה הכי מתאים בחולון", r)["listing_ids"] == ["a", "b"]
    assert "price outside range" in answer("למה נפסלו מודעות?", r)["answer"]
    assert answer("יש סימני אזהרה?", r)["listing_ids"] == ["c"]
    assert answer("כמה הזדמנויות יש", r)["intent"] == "count"
    assert answer("בלי תיווך", r)["listing_ids"] == ["a"]
    assert report(r)["total"] == 4 and report(r)["price"]["max"] == 9000 and report([])["price"] is None
    assert "ציון 90%" in explain({"score": 90, "detail": {"label": "excellent", "highlights": ["No broker"]}, "risks": []})

def test_feed_suggestions_and_query():
    from app.feeds import suggest, build_query
    p = {"category": "real_estate", "location": "Holon", "name": "x", "required_keywords": ["3", "חניה"]}
    assert build_query(p).startswith("דירה חולון")
    s = suggest(p); assert any(x["kind"] == "rss" and "bing.com" in x["url"] for x in s)
    assert all(x["kind"] in ("rss", "jsonfeed", "jsonld", "csv", "reddit", "tgpublic") for x in s)
    assert [x for x in s if x.get("needs_input")] and all("url" in x for x in s if not x.get("needs_input"))

def test_llm_free_provider_presets():
    import os, json
    from app import llm
    for k in ("OPENAI_API_KEY", "GROQ_API_KEY", "LLM_PROVIDER"): os.environ.pop(k, None)
    assert not llm.configured()
    os.environ["GROQ_API_KEY"] = "g"; assert llm._cfg()[0].startswith("https://api.groq.com")
    assert llm.chat("s", "u", post=lambda u, h, j: {"choices": [{"message": {"content": " hi "}}]}) == "hi"
    assert llm.chat("s", "u", post=lambda u, h, j: 1 / 0) is None      # never raises
    os.environ.pop("GROQ_API_KEY")
