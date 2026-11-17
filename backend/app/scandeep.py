"""Scan Center engine (v3.14): the deep, parallel, self-explaining scan. Additive: scanplus.py / discovery.py are untouched and still power Scan+.
Same legal model as discovery.py: official search APIs only, title + snippet + link, result pages are never fetched.

What makes it stronger than Scan+:
* depth levels (quick / standard / deep / max) with up to 30 differently phrased queries, interleaved so even a small cap covers every angle
* fan-out: each query can be sent to several engines at once and the answers merged (a result seen by several engines or queries is more trustworthy)
* parallel workers with live progress, cancel, and a per-query / per-engine report
* every result is enriched (price, rooms, city, area, phone), checked against the search ("city ok, rooms ok, over budget") and graded A-D
* market read-out (median, cheapest, deals under the median) and plain-language insights
Pure functions + an injectable `searcher`, so tests need no network."""
import re, statistics, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

DEPTHS = {
    "quick": {"label": "מהירה", "queries": 6, "per": 10, "fanout": 1, "import": 25, "desc": "סריקה קלה: כמה ניסוחים עיקריים ואתר מודעות אחד או שניים."},
    "standard": {"label": "רגילה", "queries": 12, "per": 10, "fanout": 2, "import": 40, "desc": "מאזנת בין כיסוי למכסה: ניסוחים, מחיר, אנגלית וכל אתרי המודעות."},
    "deep": {"label": "עמוקה", "queries": 20, "per": 12, "fanout": 3, "import": 55, "desc": "כל ניסוח אפשרי, מאפיינים, חדרים סמוכים ושאילתה לכל אתר, בכמה מנועים במקביל."},
    "max": {"label": "מקסימלית", "queries": 30, "per": 15, "fanout": 3, "import": 70, "desc": "הכי רחבה: עד 30 שאילתות בכל המנועים. צורכת הכי הרבה ממכסת החיפוש."},
}
SITES = {"real_estate": ["yad2.co.il", "madlan.co.il", "homeless.co.il", "winwin.co.il", "komo.co.il", "onmap.co.il", "yad1.co.il"],
         "vehicles": ["yad2.co.il", "icar.co.il", "carzone.co.il", "autotrader.co.il"], "electronics": ["yad2.co.il", "ksp.co.il", "zap.co.il", "ivory.co.il"], "furniture": ["yad2.co.il", "ikea.com"]}
FEATURES = {"real_estate": ["חניה", "מעלית", "מרפסת", "משופצת", "ממ״ד", "מזגנים"], "vehicles": ["אוטומט", "ק״מ נמוך", "במצב מצוין", "טסט ארוך"],
            "electronics": ["כמו חדש", "באחריות", "חדש באריזה"], "furniture": ["במצב טוב", "כמו חדש"]}
_TRACK = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_|mc_|yclid|igshid|_ga)", re.I)
_LOCK = threading.Lock()


def depth_cfg(name: str | None) -> dict:
    return {**DEPTHS.get(name or "standard", DEPTHS["standard"]), "name": name if name in DEPTHS else "standard"}


# ------------------------------------------------------------------ query planning
def _rooms(params: dict):
    from .scanplus import _rooms as r
    return r(params)


def deep_queries(params: dict, query: str | None = None, cap: int = 12) -> list[dict]:
    """-> [{query, site|None, tag}] ordered so that any prefix is diverse: core, wording, site, feature and English queries are interleaved."""
    from . import feeds
    from .extract import find_cities
    cap = max(1, min(int(cap), 40)); base = (query or "").strip() or feeds.build_query(params); cat = params.get("category") or ""
    city = feeds.hebrew_name(params.get("location")) or (feeds.hebrew_name(find_cities(query)[0]) if query and find_cities(query) else "")
    rooms = _rooms(params); mp = params.get("max_price"); rent = feeds._intent(params) == "להשכרה" if cat == "real_estate" else False
    sites = SITES.get(cat, ["yad2.co.il"]); mpf = f"{int(mp):,}" if mp else None
    core: list[tuple] = [(base, None, "core")]
    if mpf: core += [(f"{base} עד {mpf}", None, "price"), (f"{base} {mpf} ₪", None, "price")]
    wording: list[tuple] = []; english: list[tuple] = []; feat: list[tuple] = []
    if cat == "real_estate":
        r = f"{rooms} חדרים " if rooms else ""; verb = "להשכרה" if rent else "למכירה"
        wording += [(f"דירת {r}{verb} {city}".strip(), None, "wording"), (f"{city} {'שכירות' if rent else 'דירה למכירה'} {r}ללא תיווך".strip(), None, "owner"),
                    (f"{city} {r}{verb} מבעלים".strip(), None, "owner"), (f"{r}{verb} ב{city}".strip(), None, "wording")]
        english += [(f"apartment for {'rent' if rent else 'sale'} {city}".strip(), None, "english"), (f"{rooms or ''} room apartment {city} {'rent' if rent else 'for sale'}".replace("  ", " ").strip(), None, "english")]
        try:
            rv = float(rooms) if rooms else None
        except ValueError: rv = None
        if rv and rv >= 1.5:
            for alt in (rv - 0.5, rv + 0.5): wording.append((f"דירת {alt:g} חדרים {verb} {city}".strip(), None, "rooms"))
        feat += [(f"{base} {f}", None, "feature") for f in FEATURES["real_estate"]]
    elif cat == "vehicles":
        wording += [(f"{base} יד ראשונה", None, "wording"), (f"{base} מבעלים פרטי", None, "owner"), (f"{base} למכירה", None, "wording")]
        english += [(f"used car {base}", None, "english")]; feat += [(f"{base} {f}", None, "feature") for f in FEATURES["vehicles"]]
    elif cat == "electronics":
        wording += [(f"{base} יד שנייה", None, "wording"), (f"{base} למכירה", None, "wording")]; english += [(f"{base} used", None, "english")]
        feat += [(f"{base} {f}", None, "feature") for f in FEATURES["electronics"]]
    else:
        wording += [(f"{base} למכירה", None, "wording"), (f"{base} יד שנייה", None, "wording")]; feat += [(f"{base} {f}", None, "feature") for f in FEATURES.get(cat, [])]
    site_q: list[tuple] = [(base, s, "site") for s in sites]
    if mpf: site_q += [(f"{base} עד {mpf}", s, "site") for s in sites[:3]]
    groups = [core, wording, site_q, english, feat]; qs: list[tuple] = []; i = 0
    while any(groups):
        g = groups[i % len(groups)]
        if g: qs.append(g.pop(0))
        i += 1
    seen, out = set(), []
    for q, s, tag in qs:
        q = re.sub(r"\s+", " ", q).strip()
        if len(q) >= 2 and (q.lower(), s) not in seen: seen.add((q.lower(), s)); out.append({"query": q, "site": s, "tag": tag})
    return out[:cap]


# ------------------------------------------------------------------ live search (fan-out across engines)
def live_search(q: str, n: int, site: str | None, fanout: int) -> list[dict]:
    """Asks up to `fanout` engines (priority order, key rotation and cooldowns exactly like discovery.search) and merges. Each row carries its `engine`."""
    from . import discovery, pool
    engines = [e for e in discovery.ENGINES if discovery._keys_of(e)]
    if not engines: raise RuntimeError("no web search key configured")
    rows: list[dict] = []; errors: list[str] = []; asked = 0
    for e in engines:
        got = None
        for k in pool.rotate("web:" + e["name"], discovery._keys_of(e)):
            kid = f"web:{e['name']}:{pool.fp(k)}"
            if not pool.available(kid): continue
            t0 = time.monotonic()
            try:
                got = e["parse"](e["fetch"](q, n, k, **({"site": site} if site else {})) or {})
                pool.record("web:" + e["name"], True, ms=(time.monotonic() - t0) * 1000); break
            except Exception as ex:
                msg = pool.redact(f"{e['name']}: {ex}", k)
                pool.cool(kid, pool.cooldown_for(getattr(ex, "status", None), getattr(ex, "body", ""), getattr(ex, "retry_after", None)), msg); pool.record("web:" + e["name"], False, msg); errors.append(msg)
        if got is None: continue
        asked += 1; rows += [{**r, "engine": e["name"]} for r in discovery._clean(got, set())]
        if asked >= max(1, fanout): break
    if not asked: raise RuntimeError("all web search providers failed or are resting: " + "; ".join(errors[-3:])[:250])
    return rows


def run_plan(plan: list[dict], searcher=None, per: int = 10, fanout: int = 2, workers: int = 3, on_progress=None, cancel: threading.Event | None = None) -> tuple[list[dict], list[dict]]:
    """Runs every planned query in parallel. -> (batches, report). batches = [{query, site, tag, rows}], report = one entry per query (found, engines, ms, error).
    `on_progress(done, total, entry)` is called from the calling thread. Never raises unless EVERY query failed (then RuntimeError with the last reason)."""
    searcher = searcher or live_search; total = len(plan); batches: list[dict] = []; report: list[dict] = []; done = 0; last: str | None = None

    def one(p):
        t0 = time.monotonic()
        if cancel is not None and cancel.is_set(): return p, None, "cancelled", 0
        try: return p, searcher(p["query"], per, p["site"], fanout), None, int((time.monotonic() - t0) * 1000)
        except Exception as ex: return p, None, str(ex)[:140], int((time.monotonic() - t0) * 1000)

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 6))) as pool_:
        futs = [pool_.submit(one, p) for p in plan]
        for f in as_completed(futs):
            p, rows, err, ms = f.result(); done += 1
            entry = {"query": p["query"], "site": p["site"], "tag": p["tag"], "found": len(rows or []), "ms": ms, "engines": sorted({r.get("engine") for r in rows or [] if r.get("engine")})}
            if err and err != "cancelled": entry["error"] = err; last = err
            if err == "cancelled": entry["cancelled"] = True
            if rows: batches.append({**p, "rows": rows})
            report.append(entry)
            if on_progress:
                try: on_progress(done, total, entry)
                except Exception: pass
    if not batches and last and not (cancel is not None and cancel.is_set()): raise RuntimeError(last)
    return batches, report


# ------------------------------------------------------------------ merging, enrichment, grading
def normalize_url(url: str) -> str:
    try:
        p = urlparse((url or "").strip()); host = (p.hostname or "").lower().removeprefix("www.")
        q = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False) if not _TRACK.match(k)])
        return urlunparse((p.scheme.lower() or "https", host + (f":{p.port}" if p.port and p.port not in (80, 443) else ""), p.path.rstrip("/") or "/", "", q, ""))
    except Exception: return url or ""


def merge_batches(batches: list[dict]) -> list[dict]:
    """One row per normalized URL. hits = how many (query, engine) answers contained it; the richest snippet wins."""
    by: dict[str, dict] = {}
    for b in batches:
        for r in b["rows"]:
            k = normalize_url(r.get("url") or "")
            if not k: continue
            cur = by.get(k)
            if not cur: by[k] = {**r, "key": k, "hits": 1, "engines": {r.get("engine")} - {None}, "queries": [b["query"]], "tags": {b.get("tag")}}; continue
            cur["hits"] += 1; cur["engines"] |= ({r.get("engine")} - {None}); cur["tags"].add(b.get("tag"))
            if b["query"] not in cur["queries"]: cur["queries"].append(b["query"])
            if len(r.get("snippet") or "") > len(cur.get("snippet") or ""): cur["snippet"] = r["snippet"]
            if len(r.get("title") or "") > len(cur.get("title") or ""): cur["title"] = r["title"]
    return list(by.values())


def site_of(url: str) -> str:
    return (urlparse(url or "").hostname or "?").removeprefix("www.")


def fit_checks(ex: dict, params: dict) -> list[dict]:
    """Compares what the result says with what the search asked for. ok: True / False / None (the snippet does not say)."""
    from .extract import canon_city
    out = []; want_city = canon_city(params.get("location")) if params.get("location") else None
    if want_city: out.append({"k": "city", "label": "עיר", "ok": None if not ex.get("location") else ex.get("location") == want_city or want_city in (ex.get("other_locations") or [])})
    rooms = _rooms(params)
    if rooms and ex.get("category") in (None, "real_estate"):
        try: out.append({"k": "rooms", "label": "חדרים", "ok": None if ex.get("rooms") is None else abs(float(ex["rooms"]) - float(rooms)) < 0.01})
        except ValueError: pass
    mp = params.get("max_price")
    if mp: out.append({"k": "price", "label": "תקציב", "ok": None if not ex.get("price") else ex["price"] <= mp * 1.02})
    return out


def enrich(r: dict, params: dict) -> dict:
    from .extract import extract
    from .contacts import extract_contacts
    text = f"{r.get('title') or ''}\n{r.get('snippet') or ''}"
    try: ex = extract(text)
    except Exception: ex = {}
    try: c = extract_contacts(text, r.get("url")); phones = len((c or {}).get("phones") or [])
    except Exception: phones = 0
    checks = fit_checks(ex, params); ok = sum(1 for c in checks if c["ok"] is True); bad = sum(1 for c in checks if c["ok"] is False)
    score = (r.get("_rank") or 0) + min(18, (r.get("hits", 1) - 1) * 6) + min(6, (len(r.get("engines") or ()) - 1) * 3) + 4 * ok - 7 * bad
    score = int(max(0, min(100, score)))
    return {"title": (r.get("title") or "")[:140], "url": r.get("url"), "site": site_of(r.get("url") or ""), "snippet": (r.get("snippet") or "")[:260], "rank": score, "grade": grade(score),
            "why": list(r.get("_why") or []), "hits": r.get("hits", 1), "engines": sorted(r.get("engines") or []), "checks": checks, "phones": phones,
            "price": ex.get("price"), "currency": ex.get("currency"), "rooms": ex.get("rooms"), "city": ex.get("location"), "sqm": ex.get("area_sqm"), "features": (ex.get("features") or [])[:5],
            "deal_type": ex.get("deal_type"), "flags": (ex.get("flags") or [])[:3], "broker": ex.get("broker"), "urgent": bool(ex.get("urgent"))}


def grade(score: int) -> str:
    return "A" if score >= 75 else "B" if score >= 55 else "C" if score >= 35 else "D"


GRADE_HE = {"A": "התאמה מצוינת", "B": "התאמה טובה", "C": "התאמה בינונית", "D": "התאמה חלשה"}


def analyze(batches: list[dict], params: dict, query: str | None = None) -> dict:
    """-> {items (best first), merged, junk}. Uses Scan+'s junk / title-dup filter and ranking, then adds hits, checks and grades."""
    from .scanplus import rerank
    merged = merge_batches(batches); ranked = rerank(merged, params, query)
    items = sorted((enrich(r, params) for r in ranked), key=lambda x: (-x["rank"], -x["hits"]))
    return {"items": items, "merged": len(merged), "junk": len(merged) - len(ranked)}


def market(items: list[dict]) -> dict:
    """Price read-out over the results that state a price; flags results clearly under the median (deal candidates)."""
    priced = [i for i in items if i.get("price") and i["price"] > 0 and (i.get("currency") in (None, "ILS"))]
    if len(priced) < 3: return {"n": len(priced), "enough": False}
    ps = sorted(i["price"] for i in priced); med = statistics.median(ps); q = statistics.quantiles(ps, n=4) if len(ps) >= 4 else [ps[0], med, ps[-1]]
    deals = sorted((i for i in priced if i["price"] <= med * 0.88 and i["grade"] in ("A", "B")), key=lambda i: i["price"])[:6]
    return {"n": len(priced), "enough": True, "median": med, "p25": q[0], "p75": q[-1], "min": ps[0], "max": ps[-1], "deals": [{"url": d["url"], "title": d["title"], "price": d["price"], "below_pct": round((1 - d["price"] / med) * 100)} for d in deals]}


def coverage(report: list[dict], items: list[dict]) -> dict:
    sites: dict[str, int] = {}; engines: dict[str, int] = {}
    for i in items:
        sites[i["site"]] = sites.get(i["site"], 0) + 1
        for e in i.get("engines") or []: engines[e] = engines.get(e, 0) + 1
    tags: dict[str, int] = {}
    for r in report: tags[r.get("tag") or "?"] = tags.get(r.get("tag") or "?", 0) + r.get("found", 0)
    return {"sites": sorted(sites.items(), key=lambda kv: -kv[1])[:10], "engines": sorted(engines.items(), key=lambda kv: -kv[1]), "by_angle": sorted(tags.items(), key=lambda kv: -kv[1]),
            "queries_ok": sum(1 for r in report if not r.get("error") and not r.get("cancelled")), "queries_failed": sum(1 for r in report if r.get("error")), "queries_empty": sum(1 for r in report if not r.get("found") and not r.get("error"))}


ANGLE_HE = {"core": "שאילתה ראשית", "price": "עם מחיר", "wording": "ניסוח חלופי", "owner": "מבעלים / בלי תיווך", "english": "באנגלית", "site": "אתר מודעות", "feature": "מאפיין", "rooms": "חדרים סמוכים"}


def insights(items: list[dict], report: list[dict], cov: dict, mk: dict, engines_on: int, fanout: int) -> list[dict]:
    """Plain-language findings. level: good / info / warn."""
    out = []; a = sum(1 for i in items if i["grade"] == "A"); b = sum(1 for i in items if i["grade"] == "B")
    if not items: out.append({"level": "warn", "text": "לא נמצאו תוצאות שרלוונטיות. נסה סריקה עמוקה יותר, הסר מגבלת מחיר או הרחב את העיר."})
    elif a + b: out.append({"level": "good", "text": f"{a} התאמות מצוינות ו-{b} טובות מתוך {len(items)} תוצאות."})
    else: out.append({"level": "info", "text": f"נמצאו {len(items)} תוצאות אבל אף אחת לא התאימה היטב. כדאי לבדוק את החיפוש (עיר, חדרים, תקציב)."})
    multi = sum(1 for i in items if i["hits"] >= 3)
    if multi: out.append({"level": "good", "text": f"{multi} תוצאות הופיעו בשלוש שאילתות או יותר, סימן לנכס אמיתי ובולט."})
    if cov["sites"]:
        s, n = cov["sites"][0]; out.append({"level": "info", "text": f"המקור הפורה ביותר: {s} ({n} תוצאות)."})
    if cov["queries_failed"]:
        out.append({"level": "warn", "text": f"{cov['queries_failed']} שאילתות נכשלו. בדוק את מנועי החיפוש במרכז הסריקות (מפתח פג או הגיע למכסה)."})
    if engines_on == 1 and fanout > 1: out.append({"level": "warn", "text": "מוגדר רק מנוע חיפוש אחד, ולכן אין חיפוש מקביל במנועים. הוספת מנוע שני מרחיבה כיסוי."})
    if mk.get("enough"):
        out.append({"level": "info", "text": f"חציון המחירים בתוצאות: {int(mk['median']):,} ₪ (טווח {int(mk['min']):,} עד {int(mk['max']):,})."})
        if mk["deals"]: out.append({"level": "good", "text": f"{len(mk['deals'])} הזדמנויות מתחת לחציון ב-12% ומעלה."})
    risky = sum(1 for i in items if i.get("flags"))
    if risky: out.append({"level": "warn", "text": f"{risky} תוצאות עם סימני אזהרה (למשל ניסוח חשוד). בדוק לפני שיוצרים קשר."})
    return out


def csv_rows(items: list[dict]) -> list[dict]:
    return [{"דירוג": i["grade"], "ציון": i["rank"], "כותרת": i["title"], "מחיר": i.get("price") or "", "חדרים": i.get("rooms") or "", "עיר": i.get("city") or "", "אתר": i["site"], "קישור": i["url"]} for i in items]
