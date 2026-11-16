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
