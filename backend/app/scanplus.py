"""Scan+ (v3.13): a smarter way to ask the search engines and to sort what comes back. Pure helpers, no network, no DB.
Same legal model as discovery.py: only official search APIs, only title + snippet + link, never fetching result pages.
Why: one query per site misses listings phrased differently; the free engines have small quotas, so every query must earn its place."""
import re
from urllib.parse import urlparse

SITE_PACK = {"real_estate": ["yad2.co.il", "madlan.co.il", "homeless.co.il", "winwin.co.il", "komo.co.il", "onmap.co.il", "yad1.co.il"],
             "vehicles": ["yad2.co.il", "icar.co.il", "carzone.co.il"], "electronics": ["yad2.co.il", "ksp.co.il", "zap.co.il", "ivory.co.il"], "furniture": ["yad2.co.il"]}
MAX_Q_HARD = 12


def _rooms(params: dict):
    for k in params.get("required_keywords") or []:
        if re.fullmatch(r"\d(?:\.5)?", str(k).strip()): return str(k).strip()
    m = re.search(r"(\d(?:\.5)?)\s*(?:חדרים|חדר|rooms?)", str(params.get("name") or ""), re.I)
    return m.group(1) if m else None


def expand_queries(params: dict, query: str | None = None, cap: int = 8) -> list[tuple[str, str | None]]:
    """-> [(query, site|None)] best-value-first: the open query, a price-aware one, wording variants, an English one, then the classifieds sites."""
    from . import feeds
    from .extract import find_cities
    cap = max(1, min(int(cap), MAX_Q_HARD)); base = (query or "").strip() or feeds.build_query(params)
    cat = params.get("category") or ""; city = feeds.hebrew_name(params.get("location")) or (feeds.hebrew_name(find_cities(query)[0]) if query and find_cities(query) else "")
    rooms = _rooms(params); mp = params.get("max_price"); rent = feeds._intent(params) == "להשכרה" if cat == "real_estate" else False
    qs: list[tuple[str, str | None]] = [(base, None)]
    if mp: qs.append((f"{base} עד {int(mp):,}", None))
    if cat == "real_estate":
        r = f"{rooms} חדרים " if rooms else ""
        if rent: qs += [(f"דירת {r}להשכרה {city}".strip(), None), (f"{city} שכירות {r}ללא תיווך".strip(), None), (f"apartment for rent {city}", None)]
        else: qs += [(f"דירת {r}למכירה {city}".strip(), None), (f"{city} דירה למכירה מבעלים {r}".strip(), None), (f"apartment for sale {city}", None)]
    elif cat == "vehicles": qs += [(f"{base} יד ראשונה", None), (f"{base} מבעלים פרטי", None)]
    elif cat == "electronics": qs += [(f"{base} כמו חדש", None), (f"{base} באחריות", None)]
    else: qs.append((f"{base} למכירה", None))
    for s in SITE_PACK.get(cat, ["yad2.co.il"]): qs.append((base, s))
    seen, out = set(), []
    for q, s in qs:
        q = re.sub(r"\s+", " ", q).strip()
        if len(q) >= 2 and (q.lower(), s) not in seen: seen.add((q.lower(), s)); out.append((q, s))
    return out[:cap]


_JUNK_PATH = re.compile(r"/(?:search|results|category|categories|tag|tags|forum|forums|blog|articles?|news|guides?|compare)(?:/|\?|$)|[?&](?:page|p)=\d|/(?:realestate|vehicles)/?$", re.I)
_FRESH = re.compile(r"היום|אתמול|לפני\s+\d+\s+(?:שעות|שעה|דקות|ימים)|today|yesterday|just\s+listed|חדש\s+במערכת", re.I)


def junk_url(url: str) -> bool:
    """Index / search / category pages are not a single listing."""
    p = urlparse(url or ""); path = p.path or "/"
    return bool(_JUNK_PATH.search(path + ("?" + p.query if p.query else ""))) or (path.strip("/").count("/") == 0 and not p.query and path.strip("/") in ("", "realestate", "vehicles", "rent", "forsale"))


def rerank(results: list[dict], params: dict, query: str | None = None) -> list[dict]:
    """Adds _rank (0-100) and _why to each result, drops obvious junk and near-duplicate titles, returns best first."""
    from . import feeds
    from .extract import find_price
    city = (feeds.hebrew_name(params.get("location")) or "").lower(); rooms = _rooms(params); mx = params.get("max_price"); toks = {t for t in re.findall(r"[\w\u0590-\u05ff]{3,}", (query or feeds.build_query(params)).lower())}
    out, seen_titles = [], set()
    for r in results:
        text = f"{r.get('title') or ''} {r.get('snippet') or ''}"; tl = text.lower(); sc = 20.0; why = []
        if junk_url(r.get("url") or ""): sc -= 30; why.append("דף אינדקס")
        hit = sum(1 for t in toks if t in tl); sc += min(25, hit * 5)
        if city and city in tl: sc += 15; why.append("העיר מוזכרת")
        if rooms and re.search(r"(?<![\d.])" + re.escape(rooms) + r"\s*(?:חדרים|חדר|חד['׳]?|rooms?)", tl): sc += 12; why.append("מספר חדרים תואם")
        try: price = find_price(text)
        except Exception: price = None
        pv = price[0] if isinstance(price, (tuple, list)) and price else (price if isinstance(price, (int, float)) else None)
        if pv and mx:
            if pv <= mx: sc += 12; why.append("מחיר בתקציב")
            elif pv > mx * 1.15: sc -= 15; why.append("מעל התקציב")
        elif pv: sc += 5
        if re.search(r"0\d{1,2}[-\s]?\d{3}[-\s]?\d{4}", text): sc += 8; why.append("יש טלפון")
        if _FRESH.search(text): sc += 6; why.append("טרי")
        if len((r.get("snippet") or "")) < 40: sc -= 8
        key = re.sub(r"[^\w\u0590-\u05ff]+", " ", (r.get("title") or "").lower()).strip()[:60]
        if key and key in seen_titles: continue
        seen_titles.add(key)
        if sc < 5 and "דף אינדקס" in why: continue
        out.append({**r, "_rank": int(max(0, min(100, sc))), "_why": why})
    return sorted(out, key=lambda x: -x["_rank"])


def advise(engines: list[dict], queries_per_scan: int = 8) -> dict:
    """engines = discovery.status(). -> {configured, advice[], est_scans}. Free plans: Tavily about 1000/month per key, Serper about 2500 once, Brave monthly free tier."""
    on = [e for e in engines if e.get("configured")]; off = [e for e in engines if not e.get("configured")]; adv = []
    free_month = {"tavily": 1000, "brave": 1000, "serper": 2500, "exa": 1000, "jina": 1000, "google_cse": 3000}
    quota = sum(free_month.get(e["name"], 0) * max(1, e.get("keys") or 1) for e in on)
    if not on: adv.append("אין מנוע חיפוש מוגדר. הוסף מפתח חינמי אחד לפחות (Tavily או Serper).")
    if len(on) == 1: adv.append("יש רק מנוע אחד. הוספת מנוע שני מכפילה מכסה ומשלימה תוצאות כשהראשון נח.")
    for e in on:
        if e.get("keys_cooling"): adv.append(f"{e['name']}: מפתח נח כרגע (הגיע למכסה), המערכת עברה לבא.")
        if e.get("fail", 0) > 3 and e.get("fail", 0) > e.get("ok", 0): adv.append(f"{e['name']}: הרבה כשלונות ({e['fail']}). בדוק את המפתח בניהול > מוחות.")
        if e.get("keys", 1) == 1 and e["name"] in free_month: adv.append(f"{e['name']}: מפתח שני מאותו מנוע מוסיף עוד מכסה חינמית (מפרידים בפסיק).")
    if off:
        best = next((e for e in off if e["name"] in ("serper", "brave", "exa")), off[0]); adv.append(f"המלצה: להוסיף {best['name']} ({best['note']}) דרך {best['signup']}")
    est = int(quota / max(1, queries_per_scan)) if quota else 0
    return {"configured": [e["name"] for e in on], "est_free_queries_per_month": quota, "est_scans_per_month": est, "queries_per_scan": queries_per_scan, "advice": adv[:8]}


def summarize(report: list[dict], results: list[dict], imported: dict | None = None) -> dict:
    """Plain-language summary of one scan: what each query found and which sites paid off."""
    by_site: dict[str, int] = {}
    for r in results: h = (urlparse(r.get("url") or "").hostname or "?").removeprefix("www."); by_site[h] = by_site.get(h, 0) + 1
    failed = [q for q in report if q.get("error")]; yielded = sorted(report, key=lambda q: -q.get("found", 0))
    out = {"queries": len(report), "failed": len(failed), "results": len(results), "top_sites": sorted(by_site.items(), key=lambda kv: -kv[1])[:6], "best_query": yielded[0]["query"] if yielded and yielded[0].get("found") else None}
    if imported: out.update({k: imported.get(k, 0) for k in ("new", "rejected", "duplicates", "irrelevant", "errors")})
    out["headline"] = (f"נמצאו {len(results)} תוצאות ב-{len(report)} שאילתות" + (f", {out.get('new', 0)} הזדמנויות חדשות" if imported else "") + (f". {len(failed)} שאילתות נכשלו." if failed else "."))
    return out
