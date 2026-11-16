"""v3.7: brains + search control room (admin). Additive: every route is new and registered in main.py inside try/except, so a problem
here can never take the core API down. Never returns a key, only counts and short fingerprints."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import brains, discovery, flags
from .db import get_db
from .main import limiter
from .models import User
from .routes_v2 import need, ADMIN
from .main import current_user

router = APIRouter(); log = logging.getLogger("sniper")


@router.get("/api/admin/brains")
def brains_status(a: User = Depends(need(*ADMIN)), db: Session = Depends(get_db)):
    """Which free AI providers and search engines are configured, how many keys, who is resting, and the last error of each."""
    return {"llm": brains.status(), "search": discovery.status(), "flag_on": flags.load(db)["llm_extraction"]}


@router.post("/api/admin/brains/test")
def brains_test(a: User = Depends(need(*ADMIN))):
    """Sends one tiny request per configured AI key (max 3 per provider) and reports which really work. Uses a little free quota."""
    if not limiter.allow("brains-test:" + a.id, 3, 300): raise HTTPException(429, "בדיקה אחת בכל כמה דקות מספיקה, נסה שוב מאוחר יותר")
    return {"results": brains.ping()}


@router.post("/api/admin/brains/models/refresh")
def brains_models_refresh(a: User = Depends(need(*ADMIN))):
    """v3.12: ask every configured provider which models the key can really use (GET <base>/models) and re-rank them. Costs no model quota."""
    if not limiter.allow("brains-refresh:" + a.id, 6, 300): raise HTTPException(429, "רענון אחד בכל כמה דקות מספיק, נסה שוב מאוחר יותר")
    return {"results": brains.refresh_models(), "status": brains.status()}


try:   # v3.12: learn the available models in the background right after start-up (never blocks, never raises, off in unit tests)
    import os as _os
    if not _os.environ.get("PYTEST_CURRENT_TEST") and _os.environ.get("BRAINS_DISCOVER", "") != "0": brains.warm()
except Exception: log.info("brains warm-up skipped")


from sqlalchemy import select as _select
from . import outreach as _outreach
from .models import Listing as _Listing, SearchConfig as _SC


@router.get("/api/listings/{lid}/draft")
def listing_draft(lid: str, tone: str = "friendly", name: str = "", variant: int = 0, polish: bool = False, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """A ready-to-send first message to the owner. Nothing is sent from here: the UI opens the user's own WhatsApp / mail app."""
    l = db.get(_Listing, lid)
    if not l or l.user_id != u.id: raise HTTPException(404, "Listing not found")
    s = db.get(_SC, l.search_id)
    text = _outreach.draft(l.extracted or {}, s.category if s else None, tone, name, max(0, min(variant, 20)))
    ai = False
    if polish and limiter.allow("polish:" + u.id, 20, 3600):
        try:
            r = brains.complete(_outreach.polish_prompt(text, tone), temperature=0.7, max_tokens=300, purpose="draft")
            better = _outreach.safe_polished(text, brains.text_of(r))
            if better: text, ai = better, True
        except Exception as e: log.info("draft polish skipped: %s", type(e).__name__)
    return {"text": text, "tone": tone, "ai": ai}
