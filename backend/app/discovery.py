"""Discovery (v3.3): gets listings INTO the system in two legitimate ways.
1. Web search through an OFFICIAL search API (Brave Search or Tavily; you create a key). We store only the title, the snippet
   and the link the API returned, then run them through the normal pipeline (extract, dedupe, risks, score). We never fetch or
   scrape the result pages, so robots.txt / site terms are not touched and every listing keeps a link back to its owner.
2. Bulk paste: many listings in one go, split by '---' or blank lines.
Pure helpers + an injectable HTTP function (_http) so tests need no network."""
import html, logging, os, re
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models import User, SearchConfig

log = logging.getLogger("sniper")
MAX_RESULTS, MAX_BULK = 15, 30


def provider() -> str | None:
    if os.environ.get("BRAVE_API_KEY"): return "brave"
    if os.environ.get("TAVILY_API_KEY"): return "tavily"
    return None


def _http(method: str, url: str, headers: dict, params: dict | None = None, json: dict | None = None) -> dict:
    import httpx
    r = httpx.request(method, url, headers=headers, params=params, json=json, timeout=20)
    if r.status_code >= 400: raise RuntimeError(f"search API HTTP {r.status_code}")
    return r.json()


def _txt(s) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(s or ""))).split())


def search(query: str, n: int = 10) -> list[dict]:
    """-> [{title, url, snippet}] from the configured search API. Raises RuntimeError on provider problems or when none is configured."""
    q = _txt(query)[:200]
    if len(q) < 2: raise RuntimeError("empty query")
    n = max(1, min(int(n), MAX_RESULTS)); p = provider(); out = []
    if p == "brave":
        d = _http("GET", "https://api.search.brave.com/res/v1/web/search", {"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"},
                  params={"q": q, "count": n, "country": "IL", "search_lang": "he"})
        out = [{"title": r.get("title"), "url": r.get("url"), "snippet": r.get("description")} for r in (d.get("web") or {}).get("results", [])]
    elif p == "tavily":
        d = _http("POST", "https://api.tavily.com/search", {"Authorization": "Bearer " + os.environ["TAVILY_API_KEY"]},
                  json={"query": q, "max_results": n, "search_depth": "basic"})
        out = [{"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content")} for r in d.get("results", [])]
    else:
        raise RuntimeError("no web search key configured (BRAVE_API_KEY or TAVILY_API_KEY)")
    seen, clean = set(), []
    for r in out:
        u = str(r.get("url") or "")
        if not re.match(r"^https?://", u) or u in seen: continue
        seen.add(u); clean.append({"title": _txt(r.get("title"))[:200], "url": u[:1000], "snippet": _txt(r.get("snippet"))[:700]})
    return clean[:n]


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
                         "price": (l.extracted or {}).get("price"), "url": url})


def _summary() -> dict:
    return {"new": 0, "rejected": 0, "duplicates": 0, "errors": 0, "items": []}


def import_results(db: Session, u: User, s: SearchConfig, results: list[dict]) -> dict:
    out = _summary()
    for r in results:
        text = (r["title"] + "\n" + r["snippet"]).strip()
        if len(text) < 15: out["errors"] += 1; continue
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
