"""Source discovery (free, pure). Builds ready-to-add Scout feed URLs from a search, using only public machine-readable
endpoints. Everything still goes through the Scout guards (SSRF check, robots.txt, size/time limits): a feed that
disallows bots is simply marked ERROR in the UI. Honest scope: these are discovery feeds (news/discussions), not
scrapers of marketplaces that forbid scraping. For classified sites, use the owner-published feeds/pages you have access to."""
import re, urllib.parse
from .extract import _CITY_SRC

CAT_HE = {"real_estate": "דירה", "vehicles": "רכב", "electronics": "אלקטרוניקה", "furniture": "ריהוט"}
def hebrew_name(city: str | None):
    if not city: return None
    for a in _CITY_SRC.get(city, []):
        if any("א" <= ch <= "ת" for ch in a): return a
    return city

def _intent(params: dict) -> str:
    """rent vs sale vs generic. Real-estate searches with a monthly-looking budget (<= 20,000) or rent wording are rentals."""
    cat = params.get("category")
    blob = " ".join([str(params.get("name") or ""), *[str(k) for k in (params.get("required_keywords") or [])]])
    if cat == "real_estate":
        rent = re.search(r"שכיר|להשכרה|שכר\s*דירה|rent", blob, re.I)
        sale = re.search(r"למכירה|קנייה|לקנות|רכישה|sale|buy", blob, re.I)
        mp = params.get("max_price")
        if rent or (not sale and mp and mp <= 20000): return "להשכרה"
        return "למכירה"
    return "למכירה" if cat == "vehicles" else "מבצע"


def build_query(params: dict) -> str:
    parts = [CAT_HE.get(params.get("category") or "", "")]
    loc = hebrew_name(params.get("location"))
    if loc: parts.append(loc)
    parts.append(_intent(params))
    parts += [k for k in (params.get("required_keywords") or []) if k and not k.replace(".", "").isdigit()][:2]
    return " ".join(p for p in parts if p).strip() or (params.get("name") or "")

def suggest(params: dict) -> list[dict]:
    q = urllib.parse.quote_plus(build_query(params))
    if not q: return []
    return [
        {"id": "gnews", "kind": "rss", "label": "Google News (עברית, ישראל)", "url": f"https://news.google.com/rss/search?q={q}&hl=he&gl=IL&ceid=IL:he",
         "noise": True, "note": "חדשות, לא מודעות. לא יתווסף אוטומטית; מתאים רק למעקב אחרי כתבות."},
        {"id": "bing", "kind": "rss", "label": "Bing News RSS", "url": f"https://www.bing.com/news/search?q={q}&format=rss", "noise": True, "note": "חדשות, לא מודעות. לא יתווסף אוטומטית."},
        {"id": "reddit", "kind": "reddit", "label": "Reddit - חיפוש עדכני", "url": f"https://www.reddit.com/search.json?q={q}&sort=new&limit=50", "noise": True, "note": "דיונים ציבוריים, לא מודעות. לא יתווסף אוטומטית."},
        {"id": "tgpublic", "kind": "tgpublic", "label": "ערוץ טלגרם ציבורי", "url_template": "https://t.me/s/<שם_הערוץ>", "needs_input": True, "note": "הדבק כתובת ערוץ ציבורי לפי https://t.me/s/ + שם הערוץ."},
        {"id": "feed", "kind": "rss", "label": "RSS / JSON Feed של אתר שמפרסם פידים", "url_template": "https://<האתר>/feed", "needs_input": True, "note": "כל אתר שמפרסם RSS/Atom/JSON Feed או נתוני schema.org (kind=jsonld) כחוק."},
    ]
