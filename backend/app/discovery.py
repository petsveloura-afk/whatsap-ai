"""Discovery (v3.3): gets listings INTO the system in two legitimate ways.
1. Web search through OFFICIAL search APIs (Tavily, Serper, Brave, Exa, Jina, Google CSE or your own SearXNG; each has a free tier, several
   keys per engine rotate, and an engine that is out of quota is skipped automatically). We store only the title, the snippet
   and the link the API returned, then run them through the normal pipeline (extract, dedupe, risks, score). We never fetch or
   scrape the result pages, so robots.txt / site terms are not touched and every listing keeps a link back to its owner.
2. Bulk paste: many listings in one go, split by '---' or blank lines.
Pure helpers + an injectable HTTP function (_http) so tests need no network."""
import html, logging, os, re, time
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import User, SearchConfig
from . import pool
from .relevance import is_news_host

log = logging.getLogger("sniper")
MAX_RESULTS, MAX_BULK = 15, 30
# News / reference sites never contain contactable listings. Excluded at the search API and filtered again on import.
NEWS_DOMAINS = ["globes.co.il", "calcalist.co.il", "themarker.com", "ynet.co.il", "walla.co.il", "mako.co.il", "n12.co.il", "haaretz.co.il", "maariv.co.il",
                "israelhayom.co.il", "kan.org.il", "timesofisrael.com", "jpost.com", "wikipedia.org", "news.google.com", "bing.com"]


class SearchHTTPError(RuntimeError):
    """Search API answered with an error status. Carries the status so the key pool can decide how long to rest the key."""
    def __init__(self, status: int, body: str = "", retry_after: float | None = None):
        super().__init__(f"search API HTTP {status}"); self.status, self.body, self.retry_after = status, body, retry_after


def _http(method: str, url: str, headers: dict, params: dict | None = None, json: dict | None = None) -> dict:
    import httpx
    r = httpx.request(method, url, headers=headers, params=params, json=json, timeout=20)
    if r.status_code >= 400:
        ra = None
        try: ra = float(r.headers.get("retry-after"))
        except Exception: pass
        raise SearchHTTPError(r.status_code, (r.text or "")[:300], ra)
    return r.json()


def _txt(s) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))).split())


# ---- free search engines. Each fetch(q, n, key) -> raw JSON; each parse(raw) -> [{title,url,snippet}] ----------------------------------
def _nonews(q: str) -> str:
    return q + " " + " ".join("-site:" + d for d in NEWS_DOMAINS[:8])


def _f_brave(q, n, k):
    return _http("GET", "https://api.search.brave.com/res/v1/web/search", {"X-Subscription-Token": k, "Accept": "application/json"},
                 params={"q": _nonews(q), "count": n, "country": "IL", "search_lang": "he"})


def _f_tavily(q, n, k):
    return _http("POST", "https://api.tavily.com/search", {"Authorization": "Bearer " + k},
                 json={"query": q, "max_results": n, "search_depth": "basic", "country": "israel", "exclude_domains": NEWS_DOMAINS})


def _f_serper(q, n, k):
    return _http("POST", "https://google.serper.dev/search", {"X-API-KEY": k, "Content-Type": "application/json"}, json={"q": _nonews(q), "num": n, "gl": "il", "hl": "iw"})


def _f_exa(q, n, k):
    return _http("POST", "https://api.exa.ai/search", {"x-api-key": k, "Content-Type": "application/json"},
                 json={"query": q, "numResults": n, "type": "auto", "excludeDomains": NEWS_DOMAINS, "contents": {"text": {"maxCharacters": 600}}})


def _f_jina(q, n, k):
    return _http("GET", "https://s.jina.ai/", {"Authorization": "Bearer " + k, "Accept": "application/json", "X-Respond-With": "no-content"}, params={"q": _nonews(q), "gl": "IL", "hl": "he"})


def _f_gcse(q, n, k):
    return _http("GET", "https://www.googleapis.com/customsearch/v1", {}, params={"key": k, "cx": os.environ.get("GOOGLE_CSE_CX", ""), "q": _nonews(q), "num": min(n, 10), "gl": "il", "lr": "lang_iw"})


def _f_searx(q, n, k):
    base = os.environ.get("SEARXNG_URL", "").rstrip("/")
    return _http("GET", base + "/search", {"Accept": "application/json"}, params={"q": _nonews(q), "format": "json", "language": "he", "safesearch": 0})


_L = lambda items, t, u, s: [{"title": r.get(t), "url": r.get(u), "snippet": r.get(s)} for r in (items or []) if isinstance(r, dict)]
# Priority order. "env" = key variables (each may hold several keys: A,B,C or A_2, A_3 ...). keyless engines only need a URL.
ENGINES = [
    {"name": "brave", "env": ("BRAVE_API_KEY",), "fetch": _f_brave, "parse": lambda d: _L((d.get("web") or {}).get("results"), "title", "url", "description"),
     "signup": "https://brave.com/search/api/", "note": "מכסה חודשית חינמית (ייתכן שנדרש כרטיס אשראי לאימות)."},
    {"name": "tavily", "env": ("TAVILY_API_KEY",), "fetch": _f_tavily, "parse": lambda d: _L(d.get("results"), "title", "url", "content"),
     "signup": "https://app.tavily.com", "note": "חינם, בלי כרטיס אשראי. כ-1,000 חיפושים בחודש לכל מפתח."},
    {"name": "serper", "env": ("SERPER_API_KEY",), "fetch": _f_serper, "parse": lambda d: _L(d.get("organic"), "title", "link", "snippet"),
     "signup": "https://serper.dev", "note": "תוצאות גוגל. חבילת פתיחה חינמית (כ-2,500 חיפושים)."},
    {"name": "exa", "env": ("EXA_API_KEY",), "fetch": _f_exa, "parse": lambda d: _L(d.get("results"), "title", "url", "text"),
     "signup": "https://dashboard.exa.ai", "note": "חיפוש סמנטי. קרדיט חינמי בהרשמה."},
    {"name": "jina", "env": ("JINA_API_KEY",), "fetch": _f_jina, "parse": lambda d: _L(d.get("data"), "title", "url", "description"),
     "signup": "https://jina.ai", "note": "מפתח חינמי עם מכסת טוקנים התחלתית."},
    {"name": "google_cse", "env": ("GOOGLE_CSE_KEY",), "fetch": _f_gcse, "parse": lambda d: _L(d.get("items"), "title", "link", "snippet"), "needs": ("GOOGLE_CSE_CX",),
     "signup": "https://programmablesearchengine.google.com", "note": "100 חיפושים ביום חינם. דורש גם GOOGLE_CSE_CX. גוגל מצמצמת הרשמות חדשות, כדאי לבדוק זמינות."},
    {"name": "searxng", "env": (), "fetch": _f_searx, "parse": lambda d: _L(d.get("results"), "title", "url", "content"), "needs": ("SEARXNG_URL",), "keyless": True,
     "signup": "https://docs.searxng.org", "note": "בלי הגבלה: שרת SearXNG שלך (או מופע ציבורי עם JSON פתוח). מגדירים SEARXNG_URL."},
]
ENGINE = {e["name"]: e for e in ENGINES}
_SEARCH_PARTS = 3          # query at most this many engines for one search (merging results when the first returns few)


def _keys_of(e: dict) -> list[str]:
    if not all(os.environ.get(v) for v in e.get("needs", ())): return []
    if e.get("keyless"): return ["-"]
    return pool.keys(*e["env"])


def providers() -> list[str]:
    """Names of the configured engines, in priority order."""
    return [e["name"] for e in ENGINES if _keys_of(e)]


def provider() -> str | None:
    p = providers()
    return p[0] if p else None


def status() -> list[dict]:
    out = []
    for e in ENGINES:
        ks = _keys_of(e); st = pool.stats("web:" + e["name"])
        out.append({"name": e["name"], "configured": bool(ks), "keys": len(ks) if not e.get("keyless") else (1 if ks else 0), "keys_cooling": pool.cooling("web:" + e["name"] + ":"),
                    "env": list(e["env"]) + list(e.get("needs", ())), "signup": e["signup"], "note": e["note"],
                    "ok": st["ok"], "fail": st["fail"], "last_ok": st["last_ok"], "last_error": st["last_error"], "avg_ms": st["avg_ms"]})
    return out


def _clean(rows: list[dict], seen: set) -> list[dict]:
    out = []
    for r in rows:
        u = str(r.get("url") or "")
        if not re.match(r"^https?://", u) or u in seen: continue
        seen.add(u); out.append({"title": _txt(r.get("title"))[:200], "url": u[:1000], "snippet": _txt(r.get("snippet"))[:700]})
    return out


def search(query: str, n: int = 10) -> list[dict]:
    """-> [{title, url, snippet}] from the configured free search APIs. Several keys per engine rotate; an engine that is rate limited rests
    and the next one answers; when the first engine returns few results the next one tops them up (up to 3 engines).
    Raises RuntimeError when none is configured or every configured engine failed."""
    q = _txt(query)[:200]
    if len(q) < 2: raise RuntimeError("empty query")
    n = max(1, min(int(n), MAX_RESULTS))
    engines = [e for e in ENGINES if _keys_of(e)]
    if not engines: raise RuntimeError("no web search key configured (set one of TAVILY_API_KEY, SERPER_API_KEY, BRAVE_API_KEY, EXA_API_KEY, JINA_API_KEY, SEARXNG_URL)")
    seen: set = set(); results: list[dict] = []; errors: list[str] = []; asked = 0
    for e in engines:
        got = None
        for k in pool.rotate("web:" + e["name"], _keys_of(e)):
            kid = f"web:{e['name']}:{pool.fp(k)}"
            if not pool.available(kid): continue
            t0 = time.monotonic()
            try:
                got = e["parse"](e["fetch"](q, n, k) or {})
                pool.record("web:" + e["name"], True, ms=(time.monotonic() - t0) * 1000); break
            except Exception as ex:
                st = getattr(ex, "status", None); msg = pool.redact(f"{e['name']}: {ex}", k)
                pool.cool(kid, pool.cooldown_for(st, getattr(ex, "body", ""), getattr(ex, "retry_after", None)), msg); pool.record("web:" + e["name"], False, msg); errors.append(msg)
        if got is None: continue
        asked += 1
        results += _clean(got, seen)
        if len(results) >= min(n, 6) or asked >= _SEARCH_PARTS: break
    if not asked: raise RuntimeError("all web search providers failed or are resting: " + "; ".join(errors[-3:])[:250])
    return results[:n]


def _contacts(text, url):
    from .contacts import extract_contacts
    return extract_contacts(text, url)


def _ingest(db: Session, u: User, s: SearchConfig, text: str, url: str | None, out: dict):
    from . import main as M
    try:
        l = M.pipeline(db, u, s, text, url)
    except HTTPException as e:
        out["duplicates" if e.status_code == 409 else "errors"] += 1; db.rollback(); return
    except Exception as e:
        log.warning("discovery ingest failed: %s", type(e).__name__); out["errors"] += 1; db.rollback(); return
    out["new" if l.status == "new" else "rejected"] += 1
    out["items"].append({"id": l.id, "score": l.score, "status": l.status, "location": (l.extracted or {}).get("location"),
                         "price": (l.extracted or {}).get("price"), "url": url,
                         "title": text.strip().split("\n", 1)[0][:140], "contact": _contacts(text, url)})


def _summary() -> dict:
    return {"new": 0, "rejected": 0, "duplicates": 0, "errors": 0, "irrelevant": 0, "items": []}


def import_results(db: Session, u: User, s: SearchConfig, results: list[dict]) -> dict:
    out = _summary()
    for r in results:
        text = (r["title"] + "\n" + r["snippet"]).strip()
        if len(text) < 15: out["errors"] += 1; continue
        if is_news_host(r["url"]): out["irrelevant"] += 1; continue      # article, not a listing: never stored
        _ingest(db, u, s, text, r["url"], out)
    out["items"] = sorted(out["items"], key=lambda x: -x["score"])[:10]
    return out


def split_bulk(text: str) -> list[str]:
    parts = re.split(r"\n\s*(?:-{3,}|={3,}|_{3,})\s*\n|\n\s*\n\s*\n+", "\n" + (text or "").strip() + "\n")
    return [p.strip() for p in parts if len(p.strip()) >= 15][:MAX_BULK]


def ingest_many(db: Session, u: User, s: SearchConfig, text: str) -> dict:
    out = _summary(); parts = split_bulk(text); out["parsed"] = len(parts)
    for p in parts: _ingest(db, u, s, p[:5000], None, out)
    out["items"] = sorted(out["items"], key=lambda x: -x["score"])[:10]
    return out
