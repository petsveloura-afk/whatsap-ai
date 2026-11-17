"""v3.13 pro toolkit + scan+: pure functions, no network and no DB."""
import datetime as dt
import pytest
from app import toolkit as T, scanplus as S


def test_catalog_is_consistent():
    assert len(T.FEATURES) >= 30 and len(T.FEATURE_IDS) == len(T.FEATURES)
    assert all(f["plan"] in T.PLAN_RANK and f["group"] in T.GROUPS and f["name"] and f["desc"] for f in T.FEATURES)
    assert T.access("mortgage", "starter", 0)["allowed"] and T.access("clients", "pro", 0) == {"allowed": False, "reason": "upgrade", "trial_left": 0}
    a = T.access("scan_plus", "starter", 1); assert a["allowed"] and a["trial_left"] == 2 and a["reason"] == "trial"
    assert not T.access("scan_plus", "starter", 3)["allowed"] and T.access("scan_plus", "pro", 99)["allowed"] and T.access("clients", "starter", 0, open_all=True)["allowed"]
    assert not T.access("nope", "vip", 0)["allowed"]


def test_purchase_tax_matches_2026_brackets():
    assert round(T.purchase_tax(1_900_000, "single")) == 0
    assert round(T.purchase_tax(2_500_000, "single")) == 20538 and round(T.purchase_tax(3_000_000, "single")) == 45538
    assert round(T.purchase_tax(2_500_000, "additional")) == 200000 and round(T.purchase_tax(3_000_000, "additional")) == 240000
    assert T.purchase_tax(7_000_000, "additional") > 0.08 * 6_055_070
    c = T.purchase_costs(2_500_000, "single", broker=True, down_payment=700_000)
    assert c["cash_needed"] == 700_000 + c["extra_total"] and any(i["name"].startswith("תיווך") for i in c["items"]) and "קפואות" in c["note"]
    with pytest.raises(ValueError): T.purchase_costs(0)


def test_mortgage_and_affordability():
    m = T.mortgage(2_000_000, ltv_pct=70, rate_pct=4.5, years=25, income_monthly=15000)
    assert m["loan"] == 1_400_000 and 7700 < m["monthly"] < 7900 and m["schedule"][-1]["balance"] == 0 and m["total_interest"] > 0
    assert any("כשליש" in w for w in m["warnings"]) and len(m["scenarios"]) >= 4
    assert T.mortgage(1_000_000, down_payment=100_000, kind="first")["warnings"][0].startswith("מימון")
    z = T.mortgage(1_200_000, ltv_pct=50, rate_pct=0, years=20); assert z["monthly"] == 2500
    a = T.affordability(income_monthly=25000, savings=600_000, loans_monthly=2000, kind="first")
    assert 1_500_000 < a["max_price"] < 4_000_000 and a["loan"] <= a["max_price"] * 0.75 + 1 and a["limited_by"]
    assert T.affordability(30000, 2_000_000, kind="first")["max_price"] > T.affordability(30000, 500_000, kind="first")["max_price"]
    with pytest.raises(ValueError): T.affordability(0, 100)


def test_yield_vehicle_used():
    y = T.rental_yield(2_000_000, 6000, annual_costs=6000, purchase_extra=200_000, loan=1_000_000)
    assert y["gross_yield_pct"] == 3.6 and y["payback_years"] and "monthly_cashflow" in y and y["monthly_cashflow"] < 0
    v = T.vehicle_tco(120_000, years=4, km_year=15000); assert v["total"] > 0 and v["per_month"] == round(v["total"] / 48) and v["breakdown"][0]["name"] == "פחת"
    u = T.used_price(5000, 24, "good", "phone"); assert 1000 < u["fair"] < 3500 and u["low"] < u["fair"] < u["high"]
    assert T.used_price(5000, 6, "like_new", "phone")["fair"] > u["fair"]


def test_fraud_detector_explains_itself():
    bad = T.fraud_signals("דירה מדהימה! אני בחו\"ל כרגע, צריך מקדמה בהעברה לפני שאשלח את המפתחות. רק היום! bit.ly/x", {"price": 3000}, "suspicious_low")
    assert bad["level"] == "high" and bad["risk"] >= 55 and {s["code"] for s in bad["signals"]} >= {"advance", "abroad", "urgent", "toolow", "shortlink"} and all(s["why"] for s in bad["signals"])
    ok = T.fraud_signals("להשכרה דירת 3 חדרים בחולון, קומה 2, מעלית, חניה, 5,200 ש\"ח. לתיאום צפייה 050-123-4567. הדירה משופצת ופנויה מיידית ללא בעלי חיים", {"price": 5200}, "fair")
    assert ok["level"] == "low" and ok["risk"] < 25


def test_fair_price_and_negotiation():
    comps = [5000, 5200, 5400, 5600, 5800, 6000]
    fp = T.fair_price({"price": 6800, "area_sqm": 80}, comps, [60, 62, 65, 67, 70]); assert fp["enough_data"] and fp["position"] == "מעל הטווח" and fp["price_per_sqm"] == 85 and fp["sqm_gap_pct"] > 0
    assert "note" in T.fair_price({"price": 100}, [1, 2])
    ins = {"verdict": "above_market", "gap_pct": 20, "market": {"median": 5600}}
    n = T.negotiation({"price": 6800, "urgent": True, "broker": False}, ins)
    assert n["open"] < n["target"] < n["walk_away"] <= 6800 * 1.01 and "6,800" in n["message"] and any("לחוץ" in x for x in n["levers"])
    for lang in ("en", "ru", "ar"): assert T.negotiation({"price": 6800}, ins, lang=lang)["lang"] == lang
    assert T.negotiation({"price": 3000}, {"verdict": "suspicious_low"})["open"] == 3000
    assert T.negotiation({})["enough"] is False


def test_tags_checklist_compare_clusters():
    tags = [t["code"] for t in T.smart_tags("דירה עם מעלית וחניה ומרפסת שמש, ממ\"ד, ללא תיווך. אין מחסן", {"floor": 3, "total_floors": 6, "rooms": 4, "area_sqm": 100})]
    assert {"elevator", "parking", "balcony", "safe_room", "nobroker", "floor", "rooms", "area"} <= set(tags) and "storage" not in tags
    assert len(T.checklist("real_estate")) == 3 and T.checklist("vehicles")[0]["title"] and T.checklist(None)[2]["items"]
    rows = [{"id": "a", "score": 90, "price": 5000, "area": 80, "rooms": 3, "risks": 0, "tags": 5}, {"id": "b", "score": 70, "price": 6500, "area": 70, "rooms": 3, "risks": 2, "tags": 2}]
    c = T.compare(rows); assert c["winner"] == "a" and c["ranking"][0]["total"] > c["ranking"][1]["total"]
    assert T.compare(rows, {"price": 0, "score": 0, "sqm": 0, "risk": 0, "extras": 0, "rooms": 100})["weights"]["rooms"] == 100
    with pytest.raises(ValueError): T.compare(rows[:1])
    items = [{"id": 1, "text": "דירת 3 חדרים בחולון קומה 2 מעלית חניה משופצת 5200 שח", "price": 5200, "city": "Holon", "rooms": 3, "area": 80, "score": 80},
             {"id": 2, "text": "להשכרה בחולון: דירת שלושה חדרים משופצת, קומה שנייה, עם חניה ומעלית, 5150", "price": 5150, "city": "Holon", "rooms": 3, "area": 80, "score": 75},
             {"id": 3, "text": "רכב מאזדה 3 שנת 2018 יד ראשונה", "price": 60000, "city": None, "rooms": None, "area": None, "score": 60}]
    g = T.clusters(items); assert len(g) == 1 and set(g[0]["ids"]) == {1, 2} and g[0]["cheapest"] == 2 and g[0]["price_spread"] == 50


def test_messages_are_multilingual():
    ex = {"category": "real_estate", "rooms": 3, "location": "Holon", "price": 5200}
    for lang in T.LANGS:
        for kind in T.KINDS:
            m = T.message(kind, lang, ex, offer=4900, slot="14:00"); assert m and "{" not in m
    assert "5,200 ₪" in T.message("first", "he", ex) and "4,900 ₪" in T.message("offer", "en", ex, offer=4900)
    assert T.message("first", "en", ex, tone="formal", name="Dana").startswith("Dear") and "\n" not in T.message("first", "ru", ex, tone="short")


def test_crm_reminders_rules_clients():
    now = dt.datetime(2026, 11, 16, 10, 0); crm = T.crm_update({}, "L1", stage="contacted", note="דיברנו, חוזר מחר", due="2026-11-15", now=now)
    assert crm["L1"]["stage"] == "contacted" and crm["L1"]["notes"][0]["text"].startswith("דיברנו")
    r = T.due_reminders(crm, dt.date(2026, 11, 16)); assert r[0]["overdue"] and r[0]["days"] == -1
    assert T.due_reminders(T.crm_update(crm, "L1", stage="won", now=now), dt.date(2026, 11, 16)) == []
    for bad in ({"stage": "weird"}, {"due": "tomorrow"}):
        with pytest.raises(ValueError): T.crm_update({}, "x", **bad)
    rule = T.validate_rule({"name": "חולון זול", "city": "holon", "max_price": 6000, "rooms_min": 3, "keywords": ["חניה"], "min_score": 70})
    row = {"score": 80, "extracted": {"category": "real_estate", "location": "Holon", "price": 5500, "rooms": 3}, "text": "דירה עם חניה"}
    assert T.rule_match(rule, row) and not T.rule_match({**rule, "max_price": 5000}, row) and not T.rule_match({**rule, "exclude": ["חניה"]}, row) and not T.rule_match({**rule, "active": False}, row)
    with pytest.raises(ValueError): T.validate_rule({"min_price": 9, "max_price": 1})
    cl = T.validate_client({"name": "דנה", "budget_max": 6000, "cities": ["Holon"], "rooms_min": 3, "must": ["חניה"]})
    good = T.match_client(cl, {"category": "real_estate", "location": "Holon", "price": 5500, "rooms": 3}, 80, ["חניה"]); far = T.match_client(cl, {"category": "real_estate", "location": "Haifa", "price": 5500, "rooms": 3}, 80, [])
    assert good["fit"] >= 85 and far["fit"] <= 40 and "מחוץ לאזור" in far["blockers"]
    with pytest.raises(ValueError): T.validate_client({"name": ""})


def test_reports_exports_and_paste():
    rows = [{"id": str(i), "location": "Holon", "rooms": 3, "price": 5000 + i * 100, "area": 80, "created": dt.datetime(2026, 11, 1) + dt.timedelta(days=i * 3)} for i in range(10)]
    rep = T.market_report(rows, "real_estate"); assert rep["overall"]["enough_data"] and rep["sqm"]["n"] == 10 and rep["cheapest"] and rep["trend"]
    row = {"score": 88, "status": "new", "extracted": {"category": "real_estate", "location": "Holon", "rooms": 3, "area_sqm": 80, "price": 5200, "condition": "renovated"}, "risks": ["x"], "source_url": "https://example.com/a?b=1&c=2"}
    sh = T.share_texts(row, {"name": "Dana <b>", "phone": "050-1234567"}, {"verdict": "good_deal"}); assert "88%" in sh["whatsapp"] and "050-1234567" in sh["whatsapp"] and sh["email"]["subject"].startswith("הזדמנות")
    sub, body = T.weekly_brief([row] * 3, 7); assert "1" in sub or "3" in sub and "88%" in body
    html = T.deal_sheet_html({**row, "extracted": {**row["extracted"], "location": "<script>alert(1)</script>"}}, {"verdict": "good_deal", "reason": "8% below"}, T.fraud_signals("x"), [{"label": "חניה"}], {"name": "<img src=x onerror=1>", "color": "red"})
    assert "<script>" not in html and "<img" not in html and "&lt;script&gt;" in html and "#1f6feb" in html and 'dir="rtl"' in html
    csvt = T.to_csv([{**row, "extracted": {**row["extracted"], "location": "=HYPERLINK(\"x\")"}}]); assert csvt.startswith("\ufeff") and "'=HYPERLINK" in csvt
    wa = "[16/11/2026, 10:01] דנה: דירה 3 חדרים בחולון 5200 ש\"ח 😀 +972-50-123-4567\n[16/11/2026, 10:05] יוסי: רכב מאזדה 3 שנת 2018 60,000 ש\"ח יד ראשונה\n[16/11/2026, 10:06] מנהל: <Media omitted>"
    cp = T.clean_paste(wa); assert cp["source"] == "whatsapp" and cp["found"] == 2 and "050-123-4567" in cp["parts"][0] and "😀" not in cp["parts"][0] and "5200" in cp["parts"][0]
    assert T.clean_paste("מודעה ראשונה עם הרבה פרטים כאן\n\n\nמודעה שנייה עם פרטים אחרים כאן")["found"] == 2


def test_scan_plus_queries_rerank_and_advice():
    params = {"name": "דירת 3 חדרים", "category": "real_estate", "location": "Holon", "required_keywords": ["3", "חניה"], "max_price": 6000}
    qs = S.expand_queries(params, None, cap=8); assert len(qs) == 8 and qs[0][1] is None and len({q for q in qs}) == 8 and any(s == "yad2.co.il" for _, s in qs) and any("עד 6,000" in q for q, _ in qs)
    assert len(S.expand_queries(params, "דירה בחולון", cap=3)) == 3 and S.expand_queries({"category": "vehicles"}, "מאזדה 3", cap=20)[0][0] == "מאזדה 3"
    res = [{"title": "דירת 3 חדרים להשכרה בחולון", "url": "https://www.yad2.co.il/item/abc123", "snippet": "דירת 3 חדרים בחולון, חניה, 5,500 ש\"ח לחודש, לתיאום 050-123-4567. פורסם היום"},
           {"title": "דירות להשכרה", "url": "https://www.yad2.co.il/realestate/rent", "snippet": "כל הדירות להשכרה"},
           {"title": "דירת 3 חדרים להשכרה בחולון", "url": "https://other.example/x", "snippet": "דירת 3 חדרים בחולון 9,900 ש\"ח"},
           {"title": "מדריך שכירות", "url": "https://site.example/blog/rent-guide", "snippet": "טיפים"}]
    rr = S.rerank(res, params); assert rr[0]["url"].endswith("abc123") and rr[0]["_rank"] > 50 and "יש טלפון" in rr[0]["_why"] and all("_rank" in r for r in rr) and rr[0]["_rank"] > rr[-1]["_rank"]
    assert S.junk_url("https://x.co.il/search?q=1") and not S.junk_url("https://www.yad2.co.il/item/abc123")
    adv = S.advise([{"name": "tavily", "configured": True, "keys": 1, "ok": 3, "fail": 0, "keys_cooling": 0, "note": "", "signup": ""}, {"name": "serper", "configured": False, "keys": 0, "note": "n", "signup": "https://serper.dev"}], 8)
    assert adv["est_scans_per_month"] == 125 and any("serper" in a for a in adv["advice"]) and S.advise([], 8)["advice"]
    sm = S.summarize([{"query": "a", "found": 3}, {"query": "b", "found": 0, "error": "x"}], res, {"new": 2}); assert sm["failed"] == 1 and sm["new"] == 2 and "2 הזדמנויות" in sm["headline"]
