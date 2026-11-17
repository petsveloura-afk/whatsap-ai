"""v3.14 Scan Center API (additive, no new tables; registered in main.py inside try/except so it can never take the core API down).
A scan runs as a background job (one thread, parallel queries inside it) so the browser never waits on one long request:
POST /api/scan/start -> job id, GET /api/scan/jobs/{id} (progress + live log, result when done), POST .../cancel.
Finished scans are kept per user in system_settings ('pro:<hash>:scanhist' / ':scanlast') so the last result survives a restart.
Quota model: one scan = one 'scan_plus' use of the plan (same gate as Scan+); every query costs the search engines' own free quota, which preview shows up front."""
import datetime as dt, logging, os, threading, time, uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from . import agent, discovery, flags, llm, scandeep as D, scanplus
from . import main as _m
from . import routes_v7 as P
from .db import get_db, SessionLocal
from .models import User, SearchConfig

router = APIRouter(); log = logging.getLogger("sniper")
JOBS: dict[str, dict] = {}; _JL = threading.Lock(); _CANCEL: dict[str, threading.Event] = {}
MAX_KEEP, JOB_TTL = 60, 3 * 3600


def _now() -> str: return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _purge():
    cut = time.time() - JOB_TTL
    for k in [k for k, j in JOBS.items() if j["t"] < cut and j["status"] != "running"]: JOBS.pop(k, None); _CANCEL.pop(k, None)
    while len(JOBS) > MAX_KEEP:
        k = min(JOBS, key=lambda x: JOBS[x]["t"])
        if JOBS[k]["status"] == "running": break
        JOBS.pop(k, None); _CANCEL.pop(k, None)


def _view(j: dict, full: bool = True) -> dict:
    with _JL:
        v = {k: j[k] for k in ("id", "status", "phase", "done", "total", "pct", "found", "unique", "depth", "search", "started", "finished", "error", "note") if k in j}
        v["log"] = list(j.get("log", []))[-14:]
        if full and j.get("result"): v["result"] = j["result"]
        return v


class StartIn(BaseModel):
    search_id: str; depth: str = Field("standard", pattern="^(quick|standard|deep|max)$"); query: str | None = Field(None, max_length=200)
    import_results: bool = True; ai_brief: bool = True


def _plan(s: SearchConfig, depth: str, query: str | None) -> tuple[dict, list[dict]]:
    cfg = D.depth_cfg(depth); cap = min(cfg["queries"], int(os.environ.get("SCAN_DEEP_MAX_QUERIES", "30")))
    return cfg, D.deep_queries(P._params(s), query, cap)


@router.get("/api/scan/depths")
def depths(u: User = Depends(_m.current_user)):
    return {"depths": [{"id": k, **{x: v[x] for x in ("label", "queries", "per", "fanout", "desc")}} for k, v in D.DEPTHS.items()]}


@router.post("/api/scan/preview")
def preview(b: StartIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    s = _m._own_search(db, u, b.search_id); cfg, plan = _plan(s, b.depth, b.query); st = discovery.status(); on = [e for e in st if e["configured"]]
    fan = min(cfg["fanout"], max(1, len(on)))
    return {"depth": cfg["name"], "label": cfg["label"], "plan": [{"query": p["query"], "site": p["site"], "angle": D.ANGLE_HE.get(p["tag"], p["tag"])} for p in plan], "engines": [e["name"] for e in on],
            "max_engine_calls": len(plan) * fan, "cost": f"עד {len(plan) * fan} קריאות למנועי החיפוש (סריקה אחת מהחבילה)", "ready": bool(on)}


def _brief(db: Session, items: list[dict], mk: dict, search_name: str) -> dict | None:
    """Optional AI read-out of the best results. Falls back to None (the rule-based insights are always shown)."""
    try:
        if not (agent.configured() and flags.load(db)["llm_extraction"]) or not items: return None
        top = "\n".join(f"{i['grade']} {i['rank']} | {i['title'][:90]} | {i.get('price') or '?'} | {i.get('city') or '?'} | {i['site']}" for i in items[:10])
        txt = llm.chat("אתה אנליסט מודעות. כתוב בעברית, קצר ומעשי, עד 5 נקודות: מה הכי שווה לפנות אליו ולמה, על מה להיזהר, ומה לשאול. אל תמציא נתונים שאינם ברשימה.",
                       f"חיפוש: {search_name}\nחציון מחיר: {mk.get('median') or 'לא ידוע'}\nתוצאות מובילות:\n{top}", max_chars=3000)
        return {"engine": "ai", "text": txt.strip()[:1200]} if txt else None
    except Exception as e: log.warning("scan brief failed: %s", type(e).__name__); return None


def _persist(uid: str, result: dict, light: dict):
    db = SessionLocal()
    try:
        P._save(db, uid, "scanlast", result); h = P._doc(db, uid, "scanhist"); h["items"] = ([light] + (h.get("items") or []))[:12]; P._save(db, uid, "scanhist", h)
    except Exception as e: db.rollback(); log.warning("scan persist failed: %s", type(e).__name__)
    finally: db.close()


def _run(jid: str, uid: str, sid: str, b: dict, searcher=None):
    """The worker thread. Phases: search (parallel queries) -> analyze -> import (through the normal pipeline) -> done."""
    j = JOBS[jid]; cancel = _CANCEL[jid]; db = SessionLocal(); t0 = time.monotonic()
    def upd(**k):
        with _JL: j.update(k)
    try:
        u = db.get(User, uid); s = _m._own_search(db, u, sid); params = P._params(s); cfg, plan = _plan(s, b["depth"], b.get("query"))
        on = [e for e in discovery.status() if e["configured"]]; seen: set = set()
        upd(phase="search", total=len(plan), done=0, pct=0)
        def prog(done, total, entry):
            with _JL:
                j["done"] = done; j["pct"] = int(done / max(1, total) * 70); j["log"].append(entry); j["found"] = j.get("found", 0) + entry.get("found", 0)
        batches, report = D.run_plan(plan, searcher, per=cfg["per"], fanout=min(cfg["fanout"], max(1, len(on))), workers=int(os.environ.get("SCAN_DEEP_WORKERS", "3")), on_progress=prog, cancel=cancel)
        if cancel.is_set(): upd(status="cancelled", phase="cancelled", finished=_now(), note="הסריקה בוטלה. מה שנמצא עד כאן לא יובא."); return
        upd(phase="analyze", pct=74, unique=sum(len(x["rows"]) for x in batches))
        a = D.analyze(batches, params, b.get("query")); items = a["items"]; upd(unique=len(items))
        imp = {"new": 0, "rejected": 0, "duplicates": 0, "errors": 0, "irrelevant": 0}
        if b.get("import_results", True) and items:
            upd(phase="import", pct=78); cap = cfg["import"]; todo = [i for i in items if i["grade"] != "D" or i["rank"] >= 20][:cap]; n = 0
            for it in todo:
                if cancel.is_set(): break
                row = discovery._summary(); text = (it["title"] + "\n" + it["snippet"]).strip()
                if len(text) < 15: it["import"] = {"status": "skipped"}; imp["errors"] += 1; continue
                if discovery.is_news_host(it["url"]): it["import"] = {"status": "news"}; imp["irrelevant"] += 1; continue
                discovery._ingest(db, u, s, text, it["url"], row); n += 1; upd(pct=78 + int(n / max(1, len(todo)) * 18))
                if row["items"]:
                    li = row["items"][0]; it["import"] = {"status": li["status"], "id": li["id"], "score": li["score"], "contact": li["contact"]}; imp["new" if li["status"] == "new" else "rejected"] += 1
                elif row["duplicates"]: it["import"] = {"status": "duplicate"}; imp["duplicates"] += 1
                else: it["import"] = {"status": "error"}; imp["errors"] += 1
        mk = D.market(items); cov = D.coverage(report, items); ins = D.insights(items, report, cov, mk, len(on), cfg["fanout"])
        brief = _brief(db, items, mk, s.name) if b.get("ai_brief", True) else None
        secs = round(time.monotonic() - t0, 1)
        result = {"id": jid, "at": _now(), "search": s.name, "search_id": sid, "depth": cfg["name"], "label": cfg["label"], "seconds": secs, "queries": len(plan), "found": sum(len(x["rows"]) for x in batches), "merged": a["merged"], "junk": a["junk"],
                  "kept": len(items), "import": imp, "grades": {g: sum(1 for i in items if i["grade"] == g) for g in "ABCD"}, "market": mk, "coverage": cov, "insights": ins, "ai_brief": brief,
                  "report": report, "items": items[:80], "engines": [e["name"] for e in on]}
        light = {"id": jid, "at": result["at"], "search": s.name, "depth": cfg["name"], "found": result["found"], "kept": result["kept"], "new": imp["new"], "seconds": secs,
                 "top": [{"title": i["title"][:70], "url": i["url"], "grade": i["grade"]} for i in items[:5]]}
        _persist(uid, result, light)
        with _JL: j["result"] = result
        upd(status="done", phase="done", pct=100, finished=_now())
    except Exception as e:
        db.rollback(); msg = str(e)[:240] if isinstance(e, RuntimeError) else f"שגיאה פנימית ({type(e).__name__})"; log.warning("deep scan failed: %s", type(e).__name__)
        upd(status="error", phase="error", error=msg, finished=_now())
    finally: db.close()


@router.post("/api/scan/start")
def start(b: StartIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    s = _m._own_search(db, u, b.search_id)
    if not s.active: raise HTTPException(409, "החיפוש מושהה. הפעל אותו כדי לסרוק.")
    if not discovery.provider(): raise HTTPException(503, "חיפוש ברשת לא מוגדר: הוסף מפתח חינמי אחד לפחות בשרת (TAVILY_API_KEY, SERPER_API_KEY, BRAVE_API_KEY...)")
    with _JL:
        _purge()
        if any(j["uid"] == u.id and j["status"] == "running" for j in JOBS.values()): raise HTTPException(409, "כבר רצה סריקה שלך. חכה שתסתיים או בטל אותה.")
    if not _m.limiter.allow("scandeep:" + u.id, 10, 3600): raise HTTPException(429, "מכסת הסריקות לשעה הסתיימה. נסה שוב מאוחר יותר.")
    P._use(db, u, "scan_plus")
    jid = uuid.uuid4().hex[:12]; cfg = D.depth_cfg(b.depth)
    with _JL: JOBS[jid] = {"id": jid, "uid": u.id, "status": "running", "phase": "queued", "done": 0, "total": 0, "pct": 0, "found": 0, "depth": cfg["name"], "search": s.name, "started": _now(), "log": [], "t": time.time()}
    _CANCEL[jid] = threading.Event()
    th = threading.Thread(target=_run, args=(jid, u.id, s.id, b.model_dump() if hasattr(b, "model_dump") else b.dict()), daemon=True, name="scan-" + jid); th.start()
    return {"id": jid}


def _mine(jid: str, u: User) -> dict:
    j = JOBS.get(jid)
    if not j or j["uid"] != u.id: raise HTTPException(404, "הסריקה לא נמצאה (ייתכן שהשרת הופעל מחדש). הסריקה האחרונה נשמרת בהיסטוריה.")
    return j


@router.get("/api/scan/jobs/{jid}")
def job(jid: str, u: User = Depends(_m.current_user)): return _view(_mine(jid, u))


@router.post("/api/scan/jobs/{jid}/cancel")
def cancel(jid: str, u: User = Depends(_m.current_user)):
    j = _mine(jid, u)
    if j["status"] == "running" and jid in _CANCEL: _CANCEL[jid].set()
    return {"ok": True}


@router.get("/api/scan/active")
def active(u: User = Depends(_m.current_user)):
    with _JL: j = next((x for x in JOBS.values() if x["uid"] == u.id and x["status"] == "running"), None)
    return {"job": _view(j, False) if j else None}


@router.get("/api/scan/last")
def last(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    d = P._doc(db, u.id, "scanlast"); return {"result": d or None}


@router.get("/api/scan/history")
def history(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    return {"items": P._doc(db, u.id, "scanhist").get("items", [])}


@router.get("/api/scan/engines")
def engines(u: User = Depends(_m.current_user)):
    st = discovery.status(); return {"engines": st, **scanplus.advise(st, int(os.environ.get("SCAN_DEEP_MAX_QUERIES", "30")))}


@router.post("/api/scan/engines/test")
def engines_test(u: User = Depends(_m.current_user)):
    """Admin only. One tiny live request per configured engine, so a dead key or a wrong variable shows up immediately."""
    if u.role not in P.ADMIN_ROLES: raise HTTPException(403, "למנהלים בלבד")
    if not _m.limiter.allow("scantest:" + u.id, 6, 3600): raise HTTPException(429, "בדיקות רבות מדי. נסה שוב בעוד זמן מה.")
    from . import pool
    out = []
    for e in discovery.ENGINES:
        ks = discovery._keys_of(e)
        if not ks: continue
        k = ks[0]; t0 = time.monotonic()
        try: rows = e["parse"](e["fetch"]("דירה למכירה תל אביב", 2, k) or {}); out.append({"name": e["name"], "ok": True, "results": len(rows), "ms": int((time.monotonic() - t0) * 1000)})
        except Exception as ex: out.append({"name": e["name"], "ok": False, "error": pool.redact(str(ex), k)[:160], "ms": int((time.monotonic() - t0) * 1000)})
    return {"engines": out}
