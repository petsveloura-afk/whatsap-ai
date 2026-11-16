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
