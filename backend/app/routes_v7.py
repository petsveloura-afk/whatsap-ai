"""v3.13 Pro toolkit API: 30+ sellable features (see toolkit.py) + Scan+ + automation ticks.
Additive: every route is new and registered in main.py inside try/except, so a problem here can never take the core API down.
No new tables: per-user documents live in system_settings under 'pro:<hash(user)>:<name>' (settings, crm, rules, clients, autoscan, monthly usage).
Plans: starter < pro < vip. A lower plan gets a few free trial uses per month of each paid feature (the upsell hook); PRO_OPEN=1 opens everything (testing)."""
import copy, datetime as dt, hashlib, logging, os, time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import agent, brains, discovery, flags, market, scanplus, routes_v2, routes_v3
from . import toolkit as T
from . import main as _m
from .db import get_db, SessionLocal
from .models import User, Listing, SearchConfig
from .models2 import SystemSetting, Notification

router = APIRouter(); log = logging.getLogger("sniper")
ADMIN = routes_v2.ADMIN
ADMIN_ROLES = ("admin", "super_admin")


def _now() -> dt.datetime: return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
def _naive(t): return t.replace(tzinfo=None) if t is not None and getattr(t, "tzinfo", None) else t
def _open() -> bool: return os.environ.get("PRO_OPEN") == "1"


# ---------------------------------------------------------------- per-user documents (system_settings)
def _key(uid: str, name: str) -> str: return f"pro:{hashlib.sha256(uid.encode()).hexdigest()[:20]}:{name}"[:60]
def _doc(db: Session, uid: str, name: str) -> dict:
    row = db.get(SystemSetting, _key(uid, name)); return copy.deepcopy(row.value) if row and isinstance(row.value, dict) else {}   # deep copy: editing a nested dict of the loaded value in place would hide the change from SQLAlchemy
def _save(db: Session, uid: str, name: str, value: dict):
    k = _key(uid, name); row = db.get(SystemSetting, k)
    if row: row.value = value
    else: db.add(SystemSetting(key=k, value=value))
    db.commit()


# ---------------------------------------------------------------- plan gate + metering
def _plan(db: Session, u: User) -> str: return "vip" if u.role in ADMIN_ROLES else _m._plan(db, u)


def _use(db: Session, u: User, fid: str, consume: bool = True) -> dict:
    """Checks the plan / monthly trial for a feature and meters the use. 402 carries a Hebrew upsell message the UI shows as is."""
    f = T.feature(fid)
    if not f: raise HTTPException(404, "feature not found")
    plan = _plan(db, u); name = "u" + T.month_key(); usage = _doc(db, u.id, name); used = int(usage.get(fid, 0)); acc = T.access(fid, plan, used, _open())
    if not acc["allowed"]:
        need = {"pro": "Pro", "vip": "VIP"}[f["plan"]]
        raise HTTPException(402, f"'{f['name']}' זמין בחבילת {need} ומעלה" + (f". ניצלת את {f['trial']} השימושים החינמיים של החודש." if f["trial"] else "."))
    if consume:
        usage[fid] = used + 1; usage["uid"] = u.id; _save(db, u.id, name, usage)
    return {"plan": plan, **acc, "used": used + (1 if consume else 0)}


def _own(db: Session, u: User, lid: str) -> Listing:
    l = db.get(Listing, lid)
    if not l or l.user_id != u.id: raise HTTPException(404, "Listing not found")
    return l


def _row(l: Listing) -> dict:
    return {"id": l.id, "score": l.score, "status": l.status, "extracted": l.extracted or {}, "text": l.raw_text or "", "risks": l.risks or [], "source_url": l.source_url, "created": _naive(l.created_at)}


def _brand(db: Session, u: User) -> dict: return T.brand_clean(_doc(db, u.id, "set").get("brand"))


def _comps(db: Session, u: User, ex: dict, exclude: str | None = None) -> tuple[list[float], list[float]]:
    prices = routes_v3._comps(db, u, ex, exclude); sqm = []
    for x in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(500)):
        e = x.extracted or {}
        if x.id != exclude and e.get("category") == ex.get("category") and e.get("price_per_sqm") and (not ex.get("location") or e.get("location") == ex.get("location")): sqm.append(e["price_per_sqm"])
    return prices, sqm


def _insight(db: Session, u: User, l: Listing) -> dict:
    ex = l.extracted or {}; return market.deal_insight(ex.get("price"), routes_v3._comps(db, u, ex, l.id))


def _bad(e: Exception): return HTTPException(422, str(e)[:200])


# ---------------------------------------------------------------- catalog, usage, settings
@router.get("/api/pro/catalog")
def catalog(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    plan = _plan(db, u); usage = _doc(db, u.id, "u" + T.month_key()); feats = []
    for f in T.FEATURES:
        used = int(usage.get(f["id"], 0)); a = T.access(f["id"], plan, used, _open()); feats.append({**f, "allowed": a["allowed"], "reason": a["reason"], "trial_left": a["trial_left"], "used": used})
    return {"plan": plan, "month": T.month_key(), "open_all": _open(), "groups": T.GROUPS, "features": feats, "langs": T.LANGS, "kinds": T.KINDS, "stages": [{"id": i, "label": l} for i, l in T.STAGES], "rule_limit": T.MAX_RULES.get(plan, 2),
            "ai_live": agent.configured() and flags.load(db)["llm_extraction"]}


class BrandIn(BaseModel):
    name: str = Field("", max_length=60); phone: str = Field("", max_length=20); email: str = Field("", max_length=80); tagline: str = Field("", max_length=100); color: str = Field("#1f6feb", max_length=7)


@router.get("/api/pro/settings")
def settings_get(u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return {"brand": _brand(db, u)}


@router.put("/api/pro/settings")
def settings_put(b: BrandIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "white_label", consume=False); d = _doc(db, u.id, "set"); d["brand"] = T.brand_clean(b.model_dump() if hasattr(b, "model_dump") else b.dict()); _save(db, u.id, "set", d); return {"brand": d["brand"]}


# ---------------------------------------------------------------- calculators (no listing needed)
class MortgageIn(BaseModel):
    price: float = Field(gt=0, le=1e9); down_payment: float | None = Field(None, ge=0); ltv_pct: float | None = Field(None, ge=0, le=100); rate_pct: float = Field(4.5, ge=0, le=25)
    years: float = Field(25, ge=1, le=40); income_monthly: float = Field(0, ge=0, le=1e7); kind: str = Field("first", pattern="^(first|upgrade|investment)$")


class AffordIn(BaseModel):
    income_monthly: float = Field(gt=0, le=1e7); savings: float = Field(ge=0, le=1e10); loans_monthly: float = Field(0, ge=0, le=1e7); kind: str = Field("first", pattern="^(first|upgrade|investment)$")
    rate_pct: float = Field(4.5, ge=0, le=25); years: float = Field(25, ge=1, le=40); pti_pct: float = Field(33, ge=10, le=50); broker: bool = False


class CostsIn(BaseModel):
    price: float = Field(gt=0, le=1e10); kind: str = Field("single", pattern="^(single|additional)$"); broker: bool = False; lawyer_pct: float = Field(0.5, ge=0, le=3); broker_pct: float = Field(2.0, ge=0, le=5)
    appraiser: float = Field(0, ge=0, le=1e6); renovation: float = Field(0, ge=0, le=1e8); moving: float = Field(0, ge=0, le=1e6); down_payment: float | None = Field(None, ge=0)


class YieldIn(BaseModel):
    price: float = Field(gt=0, le=1e10); monthly_rent: float = Field(gt=0, le=1e7); annual_costs: float = Field(0, ge=0, le=1e8); vacancy_pct: float = Field(4, ge=0, le=50); loan: float = Field(0, ge=0, le=1e10)
    rate_pct: float = Field(4.5, ge=0, le=25); years: float = Field(25, ge=1, le=40); kind: str = Field("investment", pattern="^(first|upgrade|investment)$")


class VehicleIn(BaseModel):
    price: float = Field(gt=0, le=1e8); years: float = Field(4, ge=0.5, le=15); km_year: float = Field(15000, ge=0, le=200000); l_per_100: float = Field(7.5, ge=0, le=40); fuel_price: float = Field(7.5, ge=0, le=30)
    insurance_year: float = Field(4500, ge=0, le=1e6); license_year: float = Field(1800, ge=0, le=1e5); maintenance_year: float = Field(3000, ge=0, le=1e6); resale_pct: float | None = Field(None, ge=0, le=100)
    loan: float = Field(0, ge=0, le=1e8); rate_pct: float = Field(5.5, ge=0, le=25)


class UsedIn(BaseModel):
    new_price: float = Field(gt=0, le=1e8); age_months: float = Field(12, ge=0, le=240); condition: str = Field("good", pattern="^(like_new|good|fair|poor)$")
    category: str = Field("other", pattern="^(phone|laptop|tv|appliance|furniture|console|other)$")


def _calc(fid: str, fn, b, u: User, db: Session):
    _use(db, u, fid); d = b.model_dump() if hasattr(b, "model_dump") else b.dict()
    try: return fn(**d)
    except ValueError as e: raise _bad(e)


@router.post("/api/pro/calc/mortgage")
def calc_mortgage(b: MortgageIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return _calc("mortgage", T.mortgage, b, u, db)
@router.post("/api/pro/calc/affordability")
def calc_afford(b: AffordIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return _calc("affordability", T.affordability, b, u, db)
@router.post("/api/pro/calc/purchase-costs")
def calc_costs(b: CostsIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return _calc("purchase_costs", T.purchase_costs, b, u, db)
@router.post("/api/pro/calc/yield")
def calc_yield(b: YieldIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return _calc("yield", T.rental_yield, b, u, db)
@router.post("/api/pro/calc/vehicle")
def calc_vehicle(b: VehicleIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return _calc("vehicle_tco", T.vehicle_tco, b, u, db)
@router.post("/api/pro/calc/used-price")
def calc_used(b: UsedIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return _calc("used_price", T.used_price, b, u, db)


# ---------------------------------------------------------------- per-listing analysis
@router.get("/api/pro/listings/{lid}/fraud")
def l_fraud(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "fraud_check"); ins = _insight(db, u, l); return T.fraud_signals(l.raw_text, l.extracted, ins.get("verdict"), ins.get("gap_pct"))


@router.get("/api/pro/listings/{lid}/fair-price")
def l_fair(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "fair_price"); prices, sqm = _comps(db, u, l.extracted or {}, l.id); return T.fair_price(l.extracted or {}, prices, sqm)


@router.get("/api/pro/listings/{lid}/negotiation")
def l_nego(lid: str, lang: str = "he", u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "negotiation"); ins = _insight(db, u, l); fr = T.fraud_signals(l.raw_text, l.extracted, ins.get("verdict"), ins.get("gap_pct")); return T.negotiation(l.extracted or {}, ins, fr, lang)


@router.get("/api/pro/listings/{lid}/tags")
def l_tags(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "smart_tags"); return {"tags": T.smart_tags(l.raw_text, l.extracted)}


@router.get("/api/pro/listings/{lid}/checklist")
def l_check(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "checklist"); return {"groups": T.checklist((l.extracted or {}).get("category"), l.extracted)}


@router.get("/api/pro/listings/{lid}/share-pack")
def l_share(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "share_pack"); return T.share_texts(_row(l), _brand(db, u), _insight(db, u, l))


def _ai_live(db: Session) -> bool: return agent.configured() and flags.load(db)["llm_extraction"]


def _rule_notes(l: Listing, ins: dict, fr: dict, tags: list) -> dict:
    """Rule-based analyst used when the AI is off or unreachable, so the feature always answers."""
    pros = [t["label"] for t in tags if t["code"] in ("parking", "elevator", "safe_room", "balcony", "renovated", "nobroker", "garden", "warranty", "service", "handone")]
    if ins.get("verdict") == "good_deal": pros.insert(0, "מחיר טוב מהשוק")
    cons = list(l.risks or [])[:4] + [s["why"] for s in fr.get("signals", [])[:3]]
    if ins.get("verdict") == "above_market": cons.insert(0, "מחיר מעל השוק")
    q = [c for g in T.checklist((l.extracted or {}).get("category"), l.extracted)[:1] for c in g["items"][:4]]
    return {"summary": f"התאמה {l.score}%. " + (ins.get("reason") or ""), "pros": pros[:6], "cons": cons[:6], "questions": q, "engine": "rules"}


class AiIn(BaseModel):
    action: str = Field("analyze", pattern="^(analyze|translate)$"); lang: str = Field("en", pattern="^(he|en|ru|ar|fr)$")


@router.post("/api/pro/listings/{lid}/ai")
def l_ai(lid: str, b: AiIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "ai_analyst" if b.action == "analyze" else "translate"); ex = l.extracted or {}; ins = _insight(db, u, l)
    fr = T.fraud_signals(l.raw_text, ex, ins.get("verdict"), ins.get("gap_pct")); tags = T.smart_tags(l.raw_text, ex); base = _rule_notes(l, ins, fr, tags)
    if not _ai_live(db) or not _m.limiter.allow("proai:" + u.id, 30, 3600):
        if b.action == "translate": return {"engine": "rules", "text": l.raw_text[:1500], "note": "ה-AI כבוי או שהמכסה לשעה הסתיימה, מוצג הטקסט המקורי."}
        return base
    try:
        if b.action == "analyze":
            msgs = [{"role": "system", "content": "You are a careful real-estate and second-hand deals analyst. Answer ONLY with a JSON object: {\"summary\": str, \"pros\": [str], \"cons\": [str], \"questions\": [str]}. Hebrew. Max 5 items per list. Do not invent facts, numbers or phone numbers that are not in the listing."},
                    {"role": "user", "content": "המודעה:\n" + l.raw_text[:2500] + f"\n\nציון התאמה: {l.score}. הערכת שוק: {ins.get('reason') or 'אין'}. סימני סיכון: {', '.join(s['why'] for s in fr['signals'][:3]) or 'אין'}."}]
            d = brains.parse_json(brains.text_of(brains.complete(msgs, json_mode=True, temperature=0.2, max_tokens=700, purpose="chat")))
            clean = lambda k: [str(x)[:200] for x in (d.get(k) or []) if str(x).strip()][:6]
            return {"summary": str(d.get("summary") or base["summary"])[:400], "pros": clean("pros") or base["pros"], "cons": clean("cons") or base["cons"], "questions": clean("questions") or base["questions"], "engine": "ai"}
        names = {"he": "Hebrew", "en": "English", "ru": "Russian", "ar": "Arabic", "fr": "French"}
        msgs = [{"role": "system", "content": f"Translate the listing to {names[b.lang]}. Keep every number, price and place name exactly. Output only the translation, no notes."}, {"role": "user", "content": l.raw_text[:2500]}]
        out = brains.text_of(brains.complete(msgs, temperature=0.1, max_tokens=900, purpose="chat")).strip()
        import re as _re
        if _re.findall(r"\d+", out) and set(_re.findall(r"\d+", out)) - set(_re.findall(r"\d+", l.raw_text.replace(",", ""))) - set(_re.findall(r"\d+", l.raw_text)): return {"engine": "rules", "text": l.raw_text[:1500], "note": "התרגום הכיל מספרים שלא במקור ונפסל. מוצג המקור."}
        return {"engine": "ai", "text": out[:2500], "lang": b.lang}
    except Exception as e:                                             # BrainsUnavailable, bad JSON...: never fail the feature
        log.info("pro ai fallback: %s", type(e).__name__)
        return base if b.action == "analyze" else {"engine": "rules", "text": l.raw_text[:1500], "note": "ה-AI לא זמין כרגע."}


class SheetIn(BaseModel): ai: bool = False


@router.get("/api/pro/listings/{lid}/sheet")
def l_sheet(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    l = _own(db, u, lid); _use(db, u, "deal_sheet"); ins = _insight(db, u, l); fr = T.fraud_signals(l.raw_text, l.extracted, ins.get("verdict"), ins.get("gap_pct")); tags = T.smart_tags(l.raw_text, l.extracted)
    notes = _rule_notes(l, ins, fr, tags); return {"filename": f"deal-{l.id[:8]}.html", "mime": "text/html", "content": T.deal_sheet_html(_row(l), ins, fr, tags, _brand(db, u), notes["pros"])}


class CompareIn(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=6); weights: dict[str, float] | None = None


@router.post("/api/pro/compare")
def compare(b: CompareIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "compare"); rows = []
    for lid in dict.fromkeys(b.ids):
        l = _own(db, u, lid); ex = l.extracted or {}; rows.append({"id": l.id, "title": f"{ex.get('location') or ''} {ex.get('rooms') or ''}".strip() or l.id[:6], "score": l.score, "price": ex.get("price"), "area": ex.get("area_sqm"),
                                                               "rooms": ex.get("rooms"), "risks": len(l.risks or []), "tags": len(T.smart_tags(l.raw_text, ex))})
    try: return T.compare(rows, b.weights)
    except ValueError as e: raise _bad(e)


@router.get("/api/pro/clusters")
def clusters(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "dup_clusters"); ls = list(db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(300))); by = {l.id: l for l in ls}
    items = [{"id": l.id, "text": l.raw_text[:600], "price": (l.extracted or {}).get("price"), "city": (l.extracted or {}).get("location"), "rooms": (l.extracted or {}).get("rooms"), "area": (l.extracted or {}).get("area_sqm"), "score": l.score} for l in ls]
    out = T.clusters(items)
    for g in out: g["items"] = [{"id": i, "score": by[i].score, "price": (by[i].extracted or {}).get("price"), "url": by[i].source_url, "location": (by[i].extracted or {}).get("location")} for i in g["ids"]]
    return {"groups": out, "scanned": len(ls)}


# ---------------------------------------------------------------- templates, smart paste
class TplIn(BaseModel):
    listing_id: str | None = None; kind: str = Field("first", pattern="^(first|followup|offer|visit|thanks)$"); lang: str = Field("he", pattern="^(he|en|ru|ar)$")
    tone: str = Field("friendly", pattern="^(friendly|formal|short)$"); name: str = Field("", max_length=40); offer: float | None = Field(None, gt=0, le=1e10); slot: str = Field("", max_length=40)


@router.post("/api/pro/templates")
def templates(b: TplIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "templates"); ex = _own(db, u, b.listing_id).extracted if b.listing_id else {}
    return {"text": T.message(b.kind, b.lang, ex, b.tone, b.name, b.offer, b.slot), "lang": b.lang, "kind": b.kind}


class PasteIn(BaseModel):
    text: str = Field(min_length=15, max_length=120000); search_id: str | None = None


@router.post("/api/pro/paste/clean")
def paste_clean(b: PasteIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "smart_paste"); res = T.clean_paste(b.text)
    if b.search_id and res["parts"]:
        s = _m._own_search(db, u, b.search_id)
        if not s.active: raise HTTPException(409, "Search is paused")
        if not _m.limiter.allow("bulk:" + u.id, 20, 3600): raise HTTPException(429, "Too many bulk imports")
        res["import"] = discovery.ingest_many(db, u, s, "\n---\n".join(res["parts"]))
    return res


# ---------------------------------------------------------------- CRM + reminders
class CrmIn(BaseModel):
    stage: str | None = None; note: str | None = Field(None, max_length=500); due: str | None = Field(None, max_length=10)


def _crm(db: Session, u: User) -> dict: return dict(_doc(db, u.id, "crm").get("items") or {})


def _crm_put(db: Session, u: User, items: dict): _save(db, u.id, "crm", {"uid": u.id, "items": items})


def _brief(l: Listing) -> dict:
    ex = l.extracted or {}; return {"id": l.id, "score": l.score, "title": f"{ex.get('location') or ''} {str(ex.get('rooms')) + ' חד׳' if ex.get('rooms') else ''}".strip() or l.id[:6], "price": ex.get("price"), "url": l.source_url}


@router.put("/api/pro/crm/{lid}")
def crm_put(lid: str, b: CrmIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _own(db, u, lid); _use(db, u, "crm")
    try: items = T.crm_update(_crm(db, u), lid, b.stage, b.note, b.due)
    except ValueError as e: raise _bad(e)
    _crm_put(db, u, items); return {"id": lid, **items[lid]}


@router.get("/api/pro/crm")
def crm_board(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "crm", consume=False); items = _crm(db, u); ls = {l.id: l for l in db.scalars(select(Listing).where(Listing.user_id == u.id, Listing.id.in_(list(items)[:500])))} if items else {}
    cols = {s: [] for s in T.STAGE_IDS}
    for lid, e in items.items():
        if lid in ls: cols[e.get("stage", "new")].append({**_brief(ls[lid]), "due": e.get("due"), "notes": len(e.get("notes") or []), "last_note": (e.get("notes") or [{}])[0].get("text"), "updated": e.get("updated")})
    return {"stages": [{"id": i, "label": lb, "items": sorted(cols[i], key=lambda x: x.get("updated") or "", reverse=True)} for i, lb in T.STAGES], "tracked": sum(len(v) for v in cols.values())}


@router.get("/api/pro/crm/{lid}")
def crm_one(lid: str, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _own(db, u, lid); return _crm(db, u).get(lid) or {"stage": "new", "notes": [], "due": None}


@router.get("/api/pro/reminders")
def reminders(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "reminders", consume=False); rem = T.due_reminders(_crm(db, u)); ls = {l.id: l for l in db.scalars(select(Listing).where(Listing.user_id == u.id, Listing.id.in_([r["listing_id"] for r in rem][:200])))} if rem else {}
    return {"items": [{**r, **(_brief(ls[r["listing_id"]]) if r["listing_id"] in ls else {})} for r in rem]}


# ---------------------------------------------------------------- alert rules
class RulesIn(BaseModel): rules: list[dict] = Field(max_length=40)


@router.get("/api/pro/rules")
def rules_get(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    return {"rules": _doc(db, u.id, "rules").get("rules") or [], "limit": T.MAX_RULES.get(_plan(db, u), 2)}


@router.put("/api/pro/rules")
def rules_put(b: RulesIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "alert_rules"); lim = 40 if _open() else T.MAX_RULES.get(_plan(db, u), 2)
    if len(b.rules) > lim: raise HTTPException(402, f"החבילה שלך מאפשרת עד {lim} כללים")
    try: rules = [T.validate_rule({**r, "id": r.get("id") or hashlib.sha1(f"{u.id}{i}{time.time()}".encode()).hexdigest()[:12]}) for i, r in enumerate(b.rules)]
    except ValueError as e: raise _bad(e)
    d = _doc(db, u.id, "rules"); _save(db, u.id, "rules", {"uid": u.id, "rules": rules, "checked": _now().isoformat(timespec="seconds"), "sent": d.get("sent") or []}); return {"rules": rules}


class RuleTestIn(BaseModel): rule: dict


@router.post("/api/pro/rules/test")
def rules_test(b: RuleTestIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "alert_rules", consume=False)
    try: rule = T.validate_rule(b.rule)
    except ValueError as e: raise _bad(e)
    hits = [_brief(l) for l in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(300)) if T.rule_match(rule, _row(l))]
    return {"rule": rule, "matches": len(hits), "sample": hits[:8]}


# ---------------------------------------------------------------- clients (brokers)
class ClientsIn(BaseModel): clients: list[dict] = Field(max_length=50)


@router.get("/api/pro/clients")
def clients_get(u: User = Depends(_m.current_user), db: Session = Depends(get_db)): return {"clients": _doc(db, u.id, "clients").get("clients") or []}


@router.put("/api/pro/clients")
def clients_put(b: ClientsIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "clients")
    try: cl = [T.validate_client({**c, "id": c.get("id") or hashlib.sha1(f"{u.id}{i}{time.time()}".encode()).hexdigest()[:12]}) for i, c in enumerate(b.clients)]
    except ValueError as e: raise _bad(e)
    _save(db, u.id, "clients", {"uid": u.id, "clients": cl}); return {"clients": cl}


@router.get("/api/pro/clients/{cid}/matches")
def client_matches(cid: str, limit: int = 8, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "clients", consume=False); c = next((x for x in _doc(db, u.id, "clients").get("clients") or [] if x.get("id") == cid), None)
    if not c: raise HTTPException(404, "Client not found")
    brand = _brand(db, u); out = []
    for l in db.scalars(select(Listing).where(Listing.user_id == u.id, Listing.status.in_(["new", "saved", "contacted"])).order_by(Listing.created_at.desc()).limit(300)):
        m = T.match_client(c, l.extracted or {}, l.score, [t["label"] for t in T.smart_tags(l.raw_text, l.extracted)])
        if m["fit"] >= 50: out.append({**_brief(l), **m})
    out = sorted(out, key=lambda x: -x["fit"])[:max(1, min(limit, 20))]
    for o in out:
        l = db.get(Listing, o["id"]); o["message"] = T.share_texts(_row(l), brand)["whatsapp"]
    return {"client": c, "matches": out}


# ---------------------------------------------------------------- reports and exports
@router.get("/api/pro/report/market")
def report_market(category: str = "real_estate", location: str | None = None, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "market_report"); rows = []
    for l in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(1000)):
        e = l.extracted or {}
        if e.get("category") == category and e.get("price"): rows.append({"id": l.id, "location": e.get("location"), "rooms": e.get("rooms"), "price": e["price"], "area": e.get("area_sqm"), "created": _naive(l.created_at)})
    return T.market_report(rows, category, location)


@router.get("/api/pro/report/weekly")
def report_weekly(days: int = 7, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "weekly_brief"); since = _now() - dt.timedelta(days=max(1, min(days, 60))); rows = [_row(l) for l in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(500)) if _naive(l.created_at) >= since]
    subj, body = T.weekly_brief(rows, days, _brand(db, u)); return {"subject": subj, "body": body, "count": len(rows)}


@router.post("/api/pro/report/weekly/send")
def report_send(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "weekly_brief", consume=False)
    if not os.environ.get("SMTP_HOST"): raise HTTPException(503, "שליחת מייל לא מוגדרת בשרת (SMTP_HOST)")
    r = report_weekly(7, u, db)
    from . import mail
    try: mail.send_mail(u.email, r["subject"], r["body"])
    except Exception as e: raise HTTPException(502, "שליחת המייל נכשלה: " + type(e).__name__)
    return {"sent": True}


@router.get("/api/pro/export/csv")
def export_csv(status: str | None = None, min_score: int = 0, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "csv_export"); crm = _crm(db, u); q = select(Listing).where(Listing.user_id == u.id, Listing.score >= max(0, min_score)).order_by(Listing.created_at.desc()).limit(5000)
    if status: q = q.where(Listing.status == status)
    rows = [{**_row(l), "stage": (crm.get(l.id) or {}).get("stage")} for l in db.scalars(q)]
    return {"filename": f"opportunities-{_now().strftime('%Y%m%d')}.csv", "mime": "text/csv;charset=utf-8", "content": T.to_csv(rows), "rows": len(rows)}


# ---------------------------------------------------------------- Scan+ and auto-scan
class ScanIn(BaseModel):
    search_id: str; query: str | None = Field(None, max_length=200); limit: int = Field(10, ge=3, le=15); queries: int = Field(8, ge=1, le=12); plan_only: bool = False; import_top: int = Field(30, ge=1, le=45)


def _params(s: SearchConfig) -> dict:
    return {"name": s.name, "category": s.category, "location": s.location, "required_keywords": s.required_keywords or [], "max_price": s.max_price}


def _do_scan(db: Session, u: User, s: SearchConfig, query: str | None, queries: int, limit: int, import_top: int) -> dict:
    """Runs the expanded queries through the same official search APIs as discovery.find, merges, re-ranks, imports the best ones."""
    params = _params(s); cap = max(1, min(queries, int(os.environ.get("SCAN_PLUS_MAX_QUERIES", "10")))); plan = scanplus.expand_queries(params, query, cap)
    merged, seen, report, ok, err = [], set(), [], 0, None
    for q, site in plan:
        try: rows = discovery.search(q, limit, site)
        except RuntimeError as e: err = e; report.append({"query": q, "site": site, "found": 0, "error": str(e)[:120]}); continue
        ok += 1; fresh = [r for r in rows if r["url"] not in seen]
        for r in fresh: seen.add(r["url"])
        merged += fresh; report.append({"query": q, "site": site, "found": len(fresh)})
    if not ok and err: raise err
    ranked = scanplus.rerank(merged, params, query); imported = discovery.import_results(db, u, s, ranked[:import_top])
    return {"report": report, "found": len(merged), "kept": len(ranked), "summary": scanplus.summarize(report, ranked, imported), "top": [{"title": r["title"][:100], "url": r["url"], "rank": r["_rank"], "why": r["_why"]} for r in ranked[:8]], **imported}


@router.post("/api/pro/scan/plus")
def scan_plus(b: ScanIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    s = _m._own_search(db, u, b.search_id); cap = min(b.queries, int(os.environ.get("SCAN_PLUS_MAX_QUERIES", "10")))
    if b.plan_only: return {"plan": [{"query": q, "site": site} for q, site in scanplus.expand_queries(_params(s), b.query, cap)], "cost": "כל שאילתה צורכת חיפוש אחד ממכסת המנוע"}
    _use(db, u, "scan_plus")
    if not discovery.provider(): raise HTTPException(503, "חיפוש ברשת לא מוגדר: הוסף מפתח חינמי אחד לפחות בשרת (TAVILY_API_KEY, SERPER_API_KEY, BRAVE_API_KEY...)")
    if not s.active: raise HTTPException(409, "Search is paused")
    if not _m.limiter.allow("scanplus:" + u.id, 6, 3600): raise HTTPException(429, "מכסת סריקות מורחבות לשעה הסתיימה")
    try: return _do_scan(db, u, s, b.query, b.queries, b.limit, b.import_top)
    except RuntimeError as e: raise HTTPException(502, str(e)[:200])


@router.get("/api/pro/scan/report")
def scan_report(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "scan_report", consume=False); st = discovery.status(); return {"engines": st, **scanplus.advise(st, int(os.environ.get("SCAN_PLUS_MAX_QUERIES", "10")))}


class AutoIn(BaseModel):
    enabled: bool = False; hours: int = Field(24, ge=6, le=168); search_ids: list[str] = Field(default_factory=list, max_length=5); queries: int = Field(6, ge=1, le=8)


@router.get("/api/pro/scan/auto")
def auto_get(u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    d = _doc(db, u.id, "autoscan"); return {"enabled": bool(d.get("enabled")), "hours": d.get("hours", 24), "search_ids": d.get("search_ids", []), "queries": d.get("queries", 6), "last": d.get("last", {}), "log": d.get("log", [])[-8:]}


@router.put("/api/pro/scan/auto")
def auto_put(b: AutoIn, u: User = Depends(_m.current_user), db: Session = Depends(get_db)):
    _use(db, u, "auto_scan")
    for sid in b.search_ids: _m._own_search(db, u, sid)
    d = _doc(db, u.id, "autoscan"); d.update(uid=u.id, enabled=b.enabled, hours=b.hours, search_ids=list(dict.fromkeys(b.search_ids)), queries=b.queries); d.setdefault("last", {}); d.setdefault("log", []); _save(db, u.id, "autoscan", d); return auto_get(u, db)


# ---------------------------------------------------------------- admin: what sells
@router.get("/api/admin/pro/overview")
def admin_overview(a: User = Depends(_m.need(*ADMIN)), db: Session = Depends(get_db)):
    suffix = ":u" + T.month_key(); totals: dict[str, int] = {}; users = 0
    for row in db.scalars(select(SystemSetting).where(SystemSetting.key.like("pro:%"), SystemSetting.key.like("%" + suffix))):
        if not isinstance(row.value, dict): continue
        users += 1
        for k, v in row.value.items():
            if k in T.FEATURE_IDS and isinstance(v, int): totals[k] = totals.get(k, 0) + v
    names = {f["id"]: f for f in T.FEATURES}
    return {"month": T.month_key(), "active_users": users, "total_uses": sum(totals.values()), "features": sorted([{"id": k, "name": names[k]["name"], "plan": names[k]["plan"], "uses": v} for k, v in totals.items()], key=lambda x: -x["uses"]), "open_all": _open()}


# ---------------------------------------------------------------- scheduler ticks (idempotent, isolated, throttled)
_T = {"t": 0.0}


def _docs(db: Session, name: str, limit: int = 200):
    return list(db.scalars(select(SystemSetting).where(SystemSetting.key.like("pro:%:" + name)).limit(limit)))


def autoscan_tick(db: Session) -> int:
    done = 0; budget = max(1, int(os.environ.get("AUTO_SCAN_MAX_PER_TICK", "2")))
    for row in _docs(db, "autoscan"):
        d = copy.deepcopy(row.value or {})
        if not d.get("enabled") or not d.get("uid"): continue
        u = db.get(User, d["uid"])
        if not u or not u.is_active: continue
        acc = T.access("auto_scan", _plan(db, u), 0, _open())
        if not acc["allowed"]: continue
        for sid in d.get("search_ids", []):
            if done >= budget: return done
            last = d.get("last", {}).get(sid)
            if last and (_now() - dt.datetime.fromisoformat(last)) < dt.timedelta(hours=int(d.get("hours", 24))): continue
            s = db.get(SearchConfig, sid)
            if not s or s.user_id != u.id or not s.active: continue
            d.setdefault("last", {})[sid] = _now().isoformat(timespec="seconds"); entry = {"at": d["last"][sid], "search": s.name}
            try: r = _do_scan(db, u, s, None, int(d.get("queries", 6)), 8, 20); entry.update(new=r.get("new", 0), found=r.get("found", 0))
            except Exception as e: db.rollback(); entry["error"] = type(e).__name__
            d["log"] = (d.get("log", []) + [entry])[-20:]; done += 1; _save(db, u.id, "autoscan", d)
    return done


def alerts_tick(db: Session) -> int:
    n = 0
    for row in _docs(db, "rules"):
        d = copy.deepcopy(row.value or {}); rules = [r for r in d.get("rules", []) if r.get("active", True)]
        if not rules or not d.get("uid"): continue
        try: since = dt.datetime.fromisoformat(d.get("checked") or "")
        except ValueError: since = _now() - dt.timedelta(days=1)
        sent = list(d.get("sent") or []); u = db.get(User, d["uid"])
        if not u or not u.is_active: continue
        for l in db.scalars(select(Listing).where(Listing.user_id == u.id).order_by(Listing.created_at.desc()).limit(200)):
            if _naive(l.created_at) <= since or l.status not in ("new", "saved") or l.id in sent: continue
            r = _row(l)
            for rule in rules:
                if rule.get("verdict") == "good_deal": r["verdict"] = _insight(db, u, l).get("verdict")
                if T.rule_match(rule, r):
                    b = _brief(l); db.add(Notification(user_id=u.id, title=f"כלל התראה: {rule['name']}"[:200], body=f"{b['title']} · {l.score}%"[:500], listing_id=l.id)); sent.append(l.id); n += 1; break
        d.update(checked=_now().isoformat(timespec="seconds"), sent=sent[-300:]); _save(db, u.id, "rules", d)
    return n


def reminders_tick(db: Session) -> int:
    n = 0
    for row in _docs(db, "crm"):
        d = copy.deepcopy(row.value or {}); items = d.get("items") or {}; uid = d.get("uid"); changed = False
        for r in T.due_reminders(items):
            e = items.get(r["listing_id"]) or {}
            if r["days"] <= 0 and not e.get("notified") and uid:
                db.add(Notification(user_id=uid, title="תזכורת מעקב", body=(r.get("last_note") or "הגיע הזמן לחזור למוכר")[:200], listing_id=r["listing_id"])); e["notified"] = True; items[r["listing_id"]] = e; n += 1; changed = True
        if changed: d["items"] = items; _save(db, uid, "crm", d)
    return n


def tick(db: Session) -> dict:
    if time.monotonic() - _T["t"] < 240: return {}
    _T["t"] = time.monotonic(); out = {}
    for name, fn in (("alerts", alerts_tick), ("reminders", reminders_tick), ("autoscan", autoscan_tick)):
        try: out[name] = fn(db)
        except Exception as e: db.rollback(); out[name] = f"error:{type(e).__name__}"; log.warning("pro tick %s failed: %s", name, type(e).__name__)
    try: db.commit()
    except Exception: db.rollback()
    return out


_installed = False


def install():
    global _installed
    if _installed: return
    _installed = True
    orig = routes_v2.schedule_due
    def schedule_with_pro(db):
        n = orig(db)
        if not os.environ.get("PYTEST_CURRENT_TEST"): tick(db)
        return n
    routes_v2.schedule_due = schedule_with_pro


install()
