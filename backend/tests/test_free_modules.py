from app.nlsearch import parse_search
from app.neardup import is_near_duplicate, embed, cosine
from app.ratelimit import Limiter

def test_nl_search_example_from_spec():
    r = parse_search("דירת 3 חדרים משופצת בחולון או בת ים, עד 5,500 ש\"ח, ללא תיווך")
    p = r["params"]
    assert p["category"] == "real_estate" and p["max_price"] == 5500
    assert set(p["locations"]) == {"Holon", "Bat Yam"}
    assert "תיווך" in p["excluded_keywords"] and r["clarifications"] == []

def test_nl_search_asks_only_when_needed():
    assert len(parse_search("something nice")["clarifications"]) == 2

def test_near_duplicate():
    a = "דירת 3 חדרים בחולון משופצת 5200 ש\"ח ללא תיווך"
    assert is_near_duplicate(a + " !", [a])
    assert not is_near_duplicate("iPhone 13 למכירה 1800 ש\"ח", [a])
    assert abs(cosine(embed(a), embed(a)) - 1) < 1e-9

def test_rate_limit():
    l = Limiter()
    assert all(l.allow("k", 3, 60) for _ in range(3)) and not l.allow("k", 3, 60) and l.allow("other", 3, 60)

def test_personalization_bounded_and_explained():
    from app.memory import adjustment, MAX_ADJ
    from app.neardup import embed
    t = "דירת 3 חדרים בחולון משופצת"
    up = adjustment(t, [embed(t)], [])
    down = adjustment(t, [], [embed(t)])
    assert 0 < up["points"] <= MAX_ADJ and -MAX_ADJ <= down["points"] < 0
    assert adjustment(t, [], [])["points"] == 0
