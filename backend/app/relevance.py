"""Relevance gate (v3.5): decides whether a piece of text is really a LISTING (something you can rent/buy/contact) or just
news / legal / discussion content that happens to mention a city. Pure functions, no network.
News and discovery feeds (Google/Bing News, web search) return many articles; without this gate an article about a court ruling
in Holon scored 77% as a "Holon apartment"."""
import re
from urllib.parse import urlparse, parse_qs, unquote

_NEWS = re.compile(
    r"בית\s*(?:ה)?משפט|עליון|מחוזי|שלום\s*בבית|עתירה|ערעור|פסק\s*דין|פסק-דין|תובע|נתבע|כתב\s*אישום|נאשם|משטרה|שוטר|נעצר|נפצע|נרצח|תאונה|שריפה|"
    r"היטל\s*השבחה|ארנונה|עירייה|עיריית|מועצת|ראש\s*העיר|כנסת|ממשלה|שר\s|בחירות|מפלגה|חדשות|דיווח|הודיע|הודיעה|פרסם|כתבה|גלובס|כלכליסט|דה\s*מרקר|"
    r"הארץ|ynet|וואלה|מעריב|ישראל\s*היום|n12|mako|walla|calcalist|themarker|haaretz|globes|breaking|court|lawsuit|ruling|police|arrested|election|minister",
    re.I)
_NEWS_HOSTS = ("news.google.com", "globes.co.il", "calcalist.co.il", "themarker.com", "ynet.co.il", "ynetnews.com", "walla.co.il", "mako.co.il", "n12.co.il",
               "haaretz.co.il", "maariv.co.il", "israelhayom.co.il", "kan.org.il", "timesofisrael.com", "jpost.com", "wikipedia.org", "facebook.com/news")
_LISTING = re.compile(
    r"להשכרה|למכירה|להשכיר|למכור|מכירה|השכרה|דמי\s*שכירות|שכ[\"״']?ד|מחיר\s*:|מחיר\s+\d|\d\s*חדרים|\d\s*חד[׳']|סטודיו|דירת\s*\d|קומה\s*\d|מ[\"״]ר|"
    r"₪|ש[\"״]ח|שקל|יד\s*שנייה|יד\s*2|לא\s*תיווך|ללא\s*תיווך|for\s*(?:rent|sale)|\brent\b|\bprice\b|\bsale\b|\$\s*\d|\d\s*\$|nis",
    re.I)


def real_url(url: str | None) -> str:
    """Bing/Google News wrap the target in a redirect (…?url=https%3a%2f%2fwww.globes.co.il…). Unwrap it for host checks."""
    if not url: return ""
    try:
        q = parse_qs(urlparse(url).query)
        for k in ("url", "u"):
            if q.get(k): return unquote(q[k][0])
    except Exception: pass
    return url


def is_news_host(url: str | None) -> bool:
    u = real_url(url) or ""
    host = (urlparse(u).hostname or "").lower().removeprefix("www.")
    full = host + (urlparse(u).path or "")
    if "bing.com/news" in (url or "").lower() or "bing.com/news" in full: return True
    return any(h in full for h in _NEWS_HOSTS)


def gate(text: str, url: str | None, ex: dict) -> tuple[int, str] | None:
    """-> None if it looks like a real listing, else (max_score, reason). The reason is stored with the listing."""
    t = text or ""
    has_price = ex.get("price") is not None
    news = bool(_NEWS.search(t)) or is_news_host(url)
    listing_words = bool(_LISTING.search(t))
    if news and not (has_price and listing_words):
        return 25, "Not a listing: looks like a news/legal article"
    if not has_price and not listing_words:
        return 35, "Not a listing: no price or sale/rent wording"
    if not has_price and ex.get("category") in ("real_estate", "vehicles", "electronics"):
        return 59, "Price missing: cannot be a strong match"
    return None
