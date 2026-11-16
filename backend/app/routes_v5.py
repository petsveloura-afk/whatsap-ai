"""v3.3: the agent API. Additive: every route is new and registered in main.py inside try/except, so a problem here
can never take the core API down. Auth, per-user isolation and rate limits reuse the existing helpers."""
import logging, os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import agent, brains, discovery, flags
from .db import Base, engine, get_db
from .main import current_user
from . import main as _m
from .models import User
from .models_agent import AgentMemory, AgentMessage

router = APIRouter(); log = logging.getLogger("sniper")
if os.environ.get("AUTO_CREATE_TABLES") == "1": Base.metadata.create_all(engine)   # dev/tests only; production uses Alembic
CHAT_LIMIT, CHAT_WINDOW = 40, 3600   # messages per user per hour


def _live(db: Session) -> bool:
    """The model is used only when a key exists AND the admin flag is on (same switch as the existing LLM features)."""
    return agent.configured() and flags.load(db)["llm_extraction"]


@router.get("/api/agent/status")
def status(u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = agent.cfg()
    return {"mode": "agent" if _live(db) else "rules", "key_configured": c is not None, "flag_on": flags.load(db)["llm_extraction"],
            "web_search": discovery.provider(), "web_searches": discovery.providers(), "provider": c["provider"] if c else None, "model": c["model"] if c else None,
            "brains": brains.status()["active"],
            "memories": len(db.scalars(select(AgentMemory.id).where(AgentMemory.user_id == u.id)).all())}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/api/agent/chat")
def chat(b: ChatIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not _m.limiter.allow("agent:" + u.id, CHAT_LIMIT, CHAT_WINDOW): raise HTTPException(429, "יותר מדי הודעות לשעה האחרונה, נסה שוב מאוחר יותר")
    msg = b.message.strip()
    if not msg: raise HTTPException(422, "Empty message")
    res, why = None, None
    if _live(db):
        try: res = agent.run(db, u, msg)
        except agent.AgentUnavailable as e:
            log.warning("agent fell back to rules: %s", e); db.rollback(); why = str(e)[:300]
    if res is None:
        res = agent.offline(db, u, msg)
        if agent.configured() and not flags.load(db)["llm_extraction"]: res["hint"] = "flag_off"
        if why: res["error"] = why   # shown in the UI so a provider problem is never silent
    agent.save_turn(db, u, msg, res["reply"], res.get("actions", []))
    agent.rollup(db, u)
    return res


@router.get("/api/agent/history")
def history(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentMessage).where(AgentMessage.user_id == u.id).order_by(AgentMessage.created_at.desc()).limit(60)).all()
    return {"items": [{"id": m.id, "role": m.role, "content": m.content, "actions": m.actions or [], "at": str(m.created_at)} for m in reversed(rows)]}


@router.delete("/api/agent/history", status_code=204)
def history_clear(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for m in db.scalars(select(AgentMessage).where(AgentMessage.user_id == u.id)): db.delete(m)
    db.commit()


@router.get("/api/agent/memory")
def memory_list(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentMemory).where(AgentMemory.user_id == u.id).order_by(AgentMemory.created_at.desc())).all()
    return {"items": [{"id": m.id, "kind": m.kind, "text": m.text, "at": str(m.created_at)} for m in rows]}


class MemIn(BaseModel):
    text: str = Field(min_length=3, max_length=500)
    kind: str = Field("fact", pattern="^(fact|preference|goal)$")


@router.post("/api/agent/memory", status_code=201)
def memory_add(b: MemIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    r = agent.remember(db, u, b.text, b.kind)
    if not r.get("saved") and r.get("reason") != "already known": raise HTTPException(422, r.get("reason", "not saved"))
    return r


@router.delete("/api/agent/memory/{mid}", status_code=204)
def memory_del(mid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not agent.forget(db, u, mid): raise HTTPException(404, "Memory item not found")


@router.delete("/api/agent/memory", status_code=204)
def memory_clear(u: User = Depends(current_user), db: Session = Depends(get_db)):
    for m in db.scalars(select(AgentMemory).where(AgentMemory.user_id == u.id)): db.delete(m)
    db.commit()


# ---- discovery: web search through an official API, and bulk paste ----
class DiscoverIn(BaseModel):
    search_id: str
    query: str | None = Field(None, max_length=200)
    limit: int = Field(10, ge=1, le=15)


@router.post("/api/agent/discover")
def discover(b: DiscoverIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _m._own_search(db, u, b.search_id)
    if not discovery.provider(): raise HTTPException(503, "חיפוש ברשת לא מוגדר: הוסף מפתח חינמי אחד לפחות בשרת (TAVILY_API_KEY, SERPER_API_KEY, BRAVE_API_KEY, EXA_API_KEY, JINA_API_KEY או SEARXNG_URL)")
    if not s.active: raise HTTPException(409, "Search is paused")
    if not _m.limiter.allow("web:" + u.id, 20, 3600): raise HTTPException(429, "מכסת חיפושי רשת לשעה הסתיימה")
    from . import feeds
    q = b.query or feeds.build_query({"name": s.name, "category": s.category, "location": s.location, "required_keywords": s.required_keywords or []})
    try: results = discovery.search(q, b.limit)
    except RuntimeError as e: raise HTTPException(502, str(e)[:200])
    return {"query": q, "results_found": len(results), **discovery.import_results(db, u, s, results)}


class BulkIn(BaseModel):
    search_id: str
    text: str = Field(min_length=15, max_length=60000)


@router.post("/api/listings/ingest-bulk")
def ingest_bulk(b: BulkIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _m._own_search(db, u, b.search_id)
    if not s.active: raise HTTPException(409, "Search is paused")
    if not _m.limiter.allow("bulk:" + u.id, 20, 3600): raise HTTPException(429, "Too many bulk imports")
    return discovery.ingest_many(db, u, s, b.text)
