"""v3.2: source discovery, free assistant, listing explanations and search reports. Additive only: every route is new,
nothing existing is touched. Registered in main.py inside try/except so a problem here can never take the core API down."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, Listing, SearchConfig
from .models2 import DataSource
from . import assistant, feeds, flags, llm, scout
from .main import current_user, _own_search
from .routes_v2 import MAX_SOURCES

router = APIRouter(); log = logging.getLogger("sniper")

def _row(l: Listing) -> dict:
    return {"id": l.id, "score": l.score, "status": l.status, "extracted": l.extracted or {}, "risks": l.risks or [],
            "detail": l.score_detail or {}, "url": l.source_url}
def _rows(db: Session, u: User, sid: str | None = None, limit: int = 300) -> list[dict]:
    q = select(Listing).where(Listing.user_id == u.id)
    if sid: q = q.where(Listing.search_id == sid)
    return [_row(l) for l in db.scalars(q.order_by(Listing.created_at.desc()).limit(limit))]
def _params(s: SearchConfig) -> dict:
    return {"name": s.name, "category": s.category, "location": s.location, "required_keywords": s.required_keywords or []}

# ---- source discovery ----
@router.get("/api/sources/suggest")
def sources_suggest(search_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, search_id)
    return {"query": feeds.build_query(_params(s)), "suggestions": feeds.suggest(_params(s))}

class ApplyIn(BaseModel):
    search_id: str
    ids: list[str] | None = None
@router.post("/api/sources/suggest/apply")
def sources_apply(b: ApplyIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_search(db, u, b.search_id)
    have = {x.url for x in db.scalars(select(DataSource).where(DataSource.user_id == u.id, DataSource.search_id == s.id))}
    count = db.scalar(select(func.count()).select_from(DataSource).where(DataSource.user_id == u.id)) or 0
    added, skipped = [], []
    for sg in feeds.suggest(_params(s)):
        if sg.get("needs_input") or (b.ids is not None and sg["id"] not in b.ids): continue
        if sg["url"] in have: skipped.append({"id": sg["id"], "reason": "already added"}); continue
        if count >= MAX_SOURCES: skipped.append({"id": sg["id"], "reason": "source limit reached"}); continue
        try: url = scout.check_url(sg["url"])
        except scout.UnsafeURL as e: skipped.append({"id": sg["id"], "reason": str(e)}); continue
        d = DataSource(user_id=u.id, search_id=s.id, kind=sg["kind"], url=url, interval_minutes=60); db.add(d); count += 1
        added.append({"id": sg["id"], "kind": sg["kind"]})
    db.commit()
    return {"added": added, "skipped": skipped}

# ---- assistant / explain / report ----
class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=400)
    search_id: str | None = None
@router.post("/api/assistant")
def ask(b: AskIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if b.search_id: _own_search(db, u, b.search_id)
    rows = _rows(db, u, b.search_id)
    res = assistant.answer(b.question, rows); res["mode"] = "rules"
    try:   # optional free LLM polish: only when a key exists AND the admin flag is on; falls back silently to rules
        if rows and llm.configured() and flags.load(db)["llm_extraction"]:
            txt = llm.chat("You are a concise Hebrew assistant for a deal-finding app. Use ONLY the facts provided. Never invent listings, prices or links. Max 6 lines.",
                           f"שאלה: {b.question}\nעובדות:\n{res['answer']}")
            if txt: res["answer"], res["mode"] = txt, "llm"
    except Exception as e: log.warning("assistant llm skipped: %s", type(e).__name__)
    return res

@router.get("/api/listings/{lid}/explain")
def explain(lid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, lid)
    if not l or l.user_id != u.id: raise HTTPException(404, "Listing not found")
    return {"listing_id": l.id, "explanation": assistant.explain(_row(l))}

@router.get("/api/searches/{sid}/report")
def search_report(sid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_search(db, u, sid)
    return assistant.report(_rows(db, u, sid, 1000))
