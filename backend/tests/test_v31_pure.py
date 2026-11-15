"""Pure tests (no FastAPI/SQLAlchemy needed): market brain, extra adapters, webhook signing, quotas."""
import datetime as dt, json
from app import market, growth, scout
from app import adapters_extra as ax
from app.extract import extract

def test_market_needs_enough_data():
    assert market.deal_insight(5000, [5000, 5100])["verdict"] == "unknown"
    assert market.deal_insight(None, [1] * 10)["verdict"] == "unknown"

def test_market_verdicts():
    prices = [5000, 5200, 5400, 5600, 5800, 6000]
    assert market.deal_insight(4800, prices)["verdict"] == "good_deal"
    assert market.deal_insight(5500, prices)["verdict"] == "fair"
    assert market.deal_insight(7000, prices)["verdict"] == "above_market"
    low = market.deal_insight(3000, prices); assert low["verdict"] == "suspicious_low" and "indicator only" in low["reason"]

def test_comparable_filters_and_trend():
    rows = [{"category": "real_estate", "location": "Holon", "rooms": 3, "price": 5000}, {"category": "real_estate", "location": "Bat Yam", "rooms": 3, "price": 4000},
            {"category": "real_estate", "location": "Holon", "rooms": 5, "price": 9000}, {"category": "cars", "location": "Holon", "rooms": None, "price": 1}]
    assert market.comparable({"category": "real_estate", "location": "Holon", "rooms": 3}, rows) == [5000]
    t = market.weekly_trend([(dt.datetime(2026, 11, 2), 100), (dt.datetime(2026, 11, 3), 300), (dt.datetime(2026, 11, 10), 50)])
    assert [x["median"] for x in t] == [200, 50]

LD = '''<html><script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Product","name":"דירת 3 חדרים בחולון","description":"משופצת, ללא תיווך","image":["https://x.example/a.jpg"],
"offers":{"@type":"Offer","price":"5200","priceCurrency":"ILS","url":"https://x.example/1"}},{"@type":"Organization","name":"nope"}]}</script></html>'''
def test_jsonld_adapter_feeds_extractor():
    items = ax.parse_jsonld(LD); assert len(items) == 1 and items[0]["image"] == "https://x.example/a.jpg" and items[0]["link"] == "https://x.example/1"
    ex = extract(scout.listing_text(items[0])); assert ex["price"] == 5200 and ex["location"] == "Holon" and ex["rooms"] == 3
def test_jsonld_ignores_bad_json():
    assert ax.parse_jsonld('<script type="application/ld+json">{oops</script>') == []

def test_csv_reddit_tg_adapters():
    c = ax.parse_csv("title,description,price,url\nדירה בחולון,3 חדרים,5200,https://x.example/1\n")
    assert c[0]["link"] == "https://x.example/1" and "5200" in c[0]["text"]
    r = ax.parse_reddit(json.dumps({"data": {"children": [{"data": {"id": "a1", "title": "iPhone 13", "selftext": "1800 ש\"ח", "permalink": "/r/x/comments/a1/"}}]}}))
    assert r[0]["link"] == "https://www.reddit.com/r/x/comments/a1/"
    tg = ax.parse_tg_public('<div class="tgme_widget_message" data-post="chan/12"><div class="tgme_widget_message_text">דירת 3 חדרים <b>בחולון</b><br/>5,200 ש"ח</div></div>')
    assert tg[0]["link"] == "https://t.me/chan/12" and "בחולון" in tg[0]["text"]
def test_new_kinds_registered_and_old_kept():
    assert {"rss", "jsonfeed", "jsonld", "csv", "reddit", "tgpublic"} <= set(scout.ADAPTERS)

def test_webhook_signature():
    s = growth.new_secret(); body = b'{"event":"ping"}'; h, ts = growth.sign(s, body)
    assert growth.verify(s, body, h) and not growth.verify(s, body + b" ", h) and not growth.verify(s, body, h, now=ts + 1000) and not growth.verify("other", body, h) and not growth.verify(s, body, "garbage")

def test_api_keys_and_quota():
    raw, prefix, h = growth.new_api_key(); assert raw.startswith("ssk_") and h == growth.hash_key(raw) and raw.startswith(prefix) and raw not in h
    assert growth.daily_quota("pro", 0) == 5000 and growth.daily_quota("starter", 3) == 200 + 300 and growth.daily_quota("starter", 999) == 200 + 100 * growth.REFERRAL_BONUS_CAP

def test_digest_hebrew_and_empty():
    s, b = growth.build_digest("dan@x.com", [{"score": 90, "location": "Holon", "price": 5200, "verdict": "good_deal"}]); assert "1" in s and "Holon" in b
    assert "אין התאמות" in growth.build_digest("a@b.c", [])[0]
