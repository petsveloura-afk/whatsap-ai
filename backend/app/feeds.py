"""Source discovery (free, pure). Builds ready-to-add Scout feed URLs from a search, using only public machine-readable
endpoints. Everything still goes through the Scout guards (SSRF check, robots.txt, size/time limits): a feed that
disallows bots is simply marked ERROR in the UI. Honest scope: these are discovery feeds (news/discussions), not
scrapers of marketplaces that forbid scraping. For classified sites, use the owner-published feeds/pages you have access to."""
import urllib.parse
from .extract import _CITY_SRC

CAT_HE = {"real_estate": "דירה", "vehicles": "רכב", "electronics": "אלקטרוניקה", "furniture": "ריהוט"}
def hebrew_name(city: str | None):
    if not city: return None
    for a in _CITY_SRC.get(city, []):
        if any("א" <= ch <= "ת" for ch in a): return a
    return city

def build_query(params: dict) -> str:
    parts = [CAT_HE.get(params.get("category") or "", "")]
    loc = hebrew_name(params.get("location"))
    if loc: parts.append(loc)
    parts.append("למכירה" if params.get("category") in ("real_estate", "vehicles") else "מבצע")
    parts += [k for k in (params.get("required_keywords") or []) if k and not k.replace(".", "").isdigit()][:2]
    return " ".join(p for p in parts if p).strip() or (params.get("name") or "")

def suggest(params: dict) -> list[dict]:
    q = urllib.parse.quote_plus(build_query(params))
    if not q: return []
    return [
        {"id": "gnews", "kind": "rss", "label": "Google News (עברית, ישראל)", "url": f"https://news.google.com/rss/search?q={q}&hl=he&gl=IL&ceid=IL:he",
         "note": "גילוי חדשות/פרסומים. אם האתר חוסם בוטים (robots.txt) המקור יסומן כשגיאה ולא ייסרק."},
        {"id": "bing", "kind": "rss", "label": "Bing News RSS", "url": f"https://www.bing.com/news/search?q={q}&format=rss", "note": "גילוי נוסף; כפוף ל-robots.txt."},
        {"id": "reddit", "kind": "reddit", "label": "Reddit - חיפוש עדכני", "url": f"https://www.reddit.com/search.json?q={q}&sort=new&limit=50", "note": "פוסטים ציבוריים; כפוף ל-robots.txt."},
        {"id": "tgpublic", "kind": "tgpublic", "label": "ערוץ טלגרם ציבורי", "url_template": "https://t.me/s/<שם_הערוץ>", "needs_input": True, "note": "הדבק כתובת ערוץ ציבורי לפי https://t.me/s/ + שם הערוץ."},
        {"id": "feed", "kind": "rss", "label": "RSS / JSON Feed של אתר שמפרסם פידים", "url_template": "https://<האתר>/feed", "needs_input": True, "note": "כל אתר שמפרסם RSS/Atom/JSON Feed או נתוני schema.org (kind=jsonld) כחוק."},
    ]
