from app.relevance import gate


def test_news_article_rejected():
    t = "העליון נגד חולון: אין לגבות היטל השבחה ממוכר דירה. בית המשפט העליון פסל ניסיון של עיריית חולון"
    assert gate(t, "http://www.bing.com/news/apiclick.aspx?url=https%3a%2f%2fwww.globes.co.il%2fx", {"price": None, "category": "real_estate"})[0] < 59


def test_real_listing_passes():
    assert gate("דירת 3 חדרים בחולון, משופצת, 5,200 ש״ח", None, {"price": 5200, "category": "real_estate"}) is None


def test_listing_without_price_capped():
    g = gate("להשכרה דירת 3 חדרים בחולון, התקשרו", None, {"price": None, "category": "real_estate"})
    assert g and g[0] == 59


def test_query_intent_and_noise_sources():
    from app.feeds import build_query, suggest
    assert build_query({"category": "real_estate", "location": "Holon", "max_price": 5500}).endswith("להשכרה")
    assert build_query({"category": "real_estate", "location": "Holon", "max_price": 2500000}).endswith("למכירה")
    assert all(x.get("noise") for x in suggest({"category": "real_estate", "location": "Holon"}) if x["id"] in ("gnews", "bing", "reddit"))


def test_news_host_helper():
    from app.relevance import is_news_host
    assert is_news_host("http://www.bing.com/news/apiclick.aspx?url=https%3a%2f%2fwww.globes.co.il%2fa") and not is_news_host("https://www.yad2.co.il/item/1")


def test_suggest_skips_sources_that_block_bots():
    from app.feeds import suggest
    ids = {x["id"] for x in suggest({"category": "real_estate", "location": "Holon"})}
    assert "gnews" not in ids and "reddit" not in ids and "bing" in ids


def test_hebrew_number_words_and_lone_budget():
    from app.nlsearch import parse_search
    f = lambda t: parse_search(t)["params"]["max_price"]
    assert f("תחפש דירת 3 חדרים עד חמש אלף שקל בחולון 5 אלף") == 5000
    assert f("דירת 3 חדרים בחולון 5 אלף") == 5000
    assert f("דירה בחולון עד עשרים וחמש אלף") == 25000
    assert f("רכב עד מאה אלף שקל") == 100000
    assert f("דירה בחולון עד אלף וחמש מאות ש\"ח") == 1500
    assert f("דירת שלוש חדרים בחולון") is None          # room count is not a budget
    assert parse_search("דירת שלוש חדרים בחולון")["params"]["required_keywords"] == ["3"]


def test_admin_has_no_search_cap_but_user_does():
    from app import main as M
    class U:  # minimal stand-in; plan lookup is bypassed for admins
        def __init__(s, role): s.role = role; s.id = "x"
    assert M.search_cap(None, U("super_admin")) > 1000 and M.search_cap(None, U("admin")) > 1000


def test_outreach_drafts_are_grammatical_and_honest():
    from app.outreach import draft, safe_polished
    x = {"rooms": 3, "location": "Holon", "price": 5200, "currency": "ILS"}
    d = draft(x, "real_estate", "friendly", "דנה")
    assert "דירת 3 חדרים בחולון" in d and "5,200" in d and d.rstrip().endswith("דנה")
    assert "ברכב" in draft({}, "vehicles", "friendly", variant=2) and "בהרכב" not in draft({}, "vehicles", "friendly", variant=2)
    assert len({draft(x, "real_estate", "friendly", variant=v) for v in range(3)}) == 3
    assert len(draft(x, "real_estate", "short")) < len(draft(x, "real_estate", "formal"))
    assert safe_polished(d, "היי, מעוניין בדירה. האם פנויה?") is not None
    assert safe_polished(d, "היי, אשלם 4,000 ₪ מיד") is None          # AI may not invent numbers


def test_draft_endpoint_isolated_and_sends_nothing():
    from tests.test_core import c, tok
    a, b = tok("dr1@x.com"), tok("dr2@x.com")
    sid = c.post("/api/searches", headers=a, json={"name": "s", "category": "real_estate", "location": "Holon", "max_price": 9000}).json()["id"]
    lid = c.post("/api/listings/ingest", headers=a, json={"search_id": sid, "text": "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח. 050-123-4567"}).json()["id"]
    r = c.get(f"/api/listings/{lid}/draft?tone=friendly&name=דנה", headers=a)
    assert r.status_code == 200 and "חולון" in r.json()["text"] and r.json()["ai"] is False
    assert "050" not in r.json()["text"]                                   # the owner's phone is never pasted into the message
    assert c.get(f"/api/listings/{lid}/draft", headers=b).status_code == 404
