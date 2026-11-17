"""Scan Center engine: pure tests, no network, no DB (a fake searcher replaces the search engines)."""
import threading
from app import scandeep as D

P = {"name": "דירת 3 חדרים בחולון", "category": "real_estate", "location": "Holon", "required_keywords": ["3"], "max_price": 5500}


def test_depth_queries_are_diverse_and_capped():
    for name, cfg in D.DEPTHS.items():
        qs = D.deep_queries(P, None, cfg["queries"])
        assert 1 <= len(qs) <= cfg["queries"]
        assert len({(q["query"].lower(), q["site"]) for q in qs}) == len(qs)
    q12 = D.deep_queries(P, None, 12)
    tags = {q["tag"] for q in q12}
    assert {"core", "site"} <= tags and len(tags) >= 4          # a small cap still covers several angles
    assert len(D.deep_queries(P, None, 30)) > len(q12)
    assert any(q["site"] == "yad2.co.il" for q in q12)


def test_vehicles_and_unknown_category():
    v = D.deep_queries({"name": "קורולה", "category": "vehicles"}, None, 20)
    assert v and all(q["query"] for q in v)
    assert D.deep_queries({"name": "x y", "category": None}, "מיטה זוגית", 5)


def test_normalize_url_strips_tracking():
    a = D.normalize_url("https://www.Yad2.co.il/item/abc/?utm_source=x&fbclid=1#top")
    assert a == D.normalize_url("https://yad2.co.il/item/abc") == "https://yad2.co.il/item/abc"
    assert D.normalize_url("https://a.com/x?id=5") != D.normalize_url("https://a.com/x?id=6")


def fake(q, n, site, fanout):
    rows = [{"title": "דירת 3 חדרים בחולון 5,200 ש\"ח", "url": "https://www.yad2.co.il/item/1?utm_source=a", "snippet": "דירת 3 חדרים בחולון משופצת להשכרה 5,200 ש\"ח לפרטים 050-123-4567 היום", "engine": "tavily"}]
    if site == "madlan.co.il": rows.append({"title": "דירת 4 חדרים בבת ים 7,900", "url": "https://madlan.co.il/x/2", "snippet": "דירת 4 חדרים בבת ים להשכרה 7,900 ש\"ח מרפסת וחניה", "engine": "serper"})
    if "fail" in q: raise RuntimeError("quota")
    return rows


def test_run_plan_parallel_progress_and_merge():
    plan = D.deep_queries(P, None, 12); seen = []
    batches, report = D.run_plan(plan, fake, per=10, fanout=2, workers=3, on_progress=lambda d, t, e: seen.append((d, t)))
    assert len(report) == len(plan) and seen[-1] == (len(plan), len(plan)) and [d for d, _ in seen] == sorted(d for d, _ in seen)
    a = D.analyze(batches, P, None); items = a["items"]
    top = items[0]
    assert top["url"].startswith("https://www.yad2") and top["hits"] >= 3 and top["grade"] in ("A", "B") and top["price"] == 5200 and top["city"] == "Holon" and top["phones"] == 1
    assert {c["k"]: c["ok"] for c in top["checks"]}["city"] is True
    wrong = next(i for i in items if "בת ים" in i["title"])
    assert {c["k"]: c["ok"] for c in wrong["checks"]}["price"] is False and wrong["rank"] < top["rank"]


def test_all_failed_raises_but_partial_does_not():
    def bad(q, n, s, f): raise RuntimeError("quota exceeded")
    try: D.run_plan(D.deep_queries(P, None, 4), bad); assert False
    except RuntimeError as e: assert "quota" in str(e)
    def half(q, n, s, f):
        if s: raise RuntimeError("x")
        return fake(q, n, s, f)
    b, r = D.run_plan(D.deep_queries(P, None, 8), half)
    assert b and any(x.get("error") for x in r)


def test_cancel_stops_work():
    ev = threading.Event(); ev.set(); calls = []
    def s(q, n, site, f): calls.append(q); return []
    b, r = D.run_plan(D.deep_queries(P, None, 6), s, cancel=ev)
    assert not calls and all(x.get("cancelled") for x in r) and b == []


def test_market_insights_and_coverage():
    items = [{"url": f"u{i}", "title": f"t{i}", "price": p, "currency": "ILS", "grade": "A", "site": "yad2.co.il", "hits": 3, "engines": ["tavily"], "rank": 80, "flags": []} for i, p in enumerate([4000, 5000, 5200, 5400, 5600])]
    mk = D.market(items)
    assert mk["enough"] and mk["median"] == 5200 and mk["deals"][0]["price"] == 4000 and mk["deals"][0]["below_pct"] == 23
    cov = D.coverage([{"query": "q", "tag": "core", "found": 5}, {"query": "z", "tag": "site", "found": 0, "error": "x"}], items)
    assert cov["queries_failed"] == 1 and cov["sites"][0] == ("yad2.co.il", 5)
    ins = D.insights(items, [], cov, mk, 1, 3)
    assert any(i["level"] == "good" for i in ins) and any("מנוע חיפוש אחד" in i["text"] for i in ins)
    assert D.market(items[:2]) == {"n": 2, "enough": False}
    assert D.insights([], [], D.coverage([], []), {"enough": False}, 0, 1)[0]["level"] == "warn"


def test_grade_bounds():
    assert [D.grade(x) for x in (100, 75, 74, 55, 35, 0)] == ["A", "A", "B", "B", "C", "D"]
