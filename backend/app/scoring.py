"""Weighted scoring + risk indicators. Backward compatible with the original contract
(score(ex, cfg, text, fresh) -> {score, factors, missing, rejection_reasons}); new keys are additive.
Fixes: numeric keywords ("3") no longer match digits inside prices, negated words ("ללא תיווך") no longer trip
an excluded "תיווך" keyword, user locations may be Hebrew or English, synonyms for renovated/broker."""
import re
from .extract import canon_city
DEFAULT_W = {"category": 25, "location": 20, "price": 25, "preference": 15, "quality": 10, "recency": 5}
_NEG = re.compile(r"(?:ללא|בלי|אין|לא|no|without|non)[\s\-]*(?:דמי\s*)?$")
_SYN = {"משופצת": ("משופץ", "משופצת", "שופצה", "renovated"), "renovated": ("משופץ", "משופצת", "שופצה", "renovated"),
        "תיווך": ("תיווך", "מתווך", "broker", "agency"), "broker": ("תיווך", "מתווך", "broker", "agency"),
        "חניה": ("חניה", "חנייה", "parking"), "מעלית": ("מעלית", "elevator", "lift"), "מרפסת": ("מרפסת", "balcony"), "ממד": ("ממד", "ממ\"ד", "safe room")}

def _present(kw: str, tl: str) -> bool:
    """keyword present and not negated just before it ('ללא תיווך' does not count as 'תיווך')."""
    kw = kw.lower().strip()
    for form in _SYN.get(kw, (kw,)):
        for m in re.finditer(re.escape(form), tl):
            if not _NEG.search(tl[max(0, m.start() - 14):m.start()]): return True
    return False

def _kw_hit(kw: str, tl: str, ex: dict) -> bool:
    k = kw.strip().lower()
    if re.fullmatch(r"\d(?:\.5)?", k):      # a rooms number: compare to extracted rooms, never to digits in the price
        if ex.get("rooms") is not None: return float(ex["rooms"]) == float(k)
        return bool(re.search(r"(?<![\d.,])" + re.escape(k) + r"\s*(?:חדרים|חדר|חד['׳]?|rooms?|br)", tl))
    if k in ("משופצת", "renovated") and ex.get("condition"): return ex["condition"] in ("renovated", "new")
    return _present(k, tl)

def risks(ex: dict, s_cfg) -> list[str]:
    r = []
    if ex.get("price") is None: r.append("Price missing")
    elif s_cfg.max_price and ex["price"] < s_cfg.max_price * 0.3: r.append("Price far below budget – verify authenticity (indicator only, not proof)")
    if ex.get("confidence", 1) < 0.4: r.append("Little structured information extracted")
    for f in ex.get("flags") or []: r.append(f + " – be careful (indicator only, not proof)")
    if ex.get("condition") == "needs_renovation": r.append("Needs renovation – factor the cost in")
    if ex.get("category") == "vehicles" and ex.get("km") and ex.get("year") and ex["km"] > 40000 * max(1, 2026 - ex["year"]) : r.append("Unusually high mileage for its age")
    return list(dict.fromkeys(r))

def score(ex: dict, cfg, text: str, fresh: float = 1.0) -> dict:
    w = {**DEFAULT_W, **(cfg.weights or {})}
    f, missing, reasons, hi = {}, [], [], []
    f["category"] = 1.0 if ex["category"] == cfg.category else (0.3 if ex["category"] is None else 0.0)
    if ex["category"] is None: missing.append("category")
    want = canon_city(cfg.location)
    if not cfg.location: f["location"] = 1.0
    elif ex["location"] is None: f["location"] = 0.3; missing.append("location")
    else:
        places = [ex["location"], *(ex.get("other_locations") or [])]
        f["location"] = 1.0 if any(str(want).lower() in p.lower() or p.lower() in str(want).lower() for p in places) else 0.0
        if f["location"] == 1.0: hi.append("Matches your area")
    p = ex["price"]
    if p is None: f["price"] = 0.3; missing.append("price")
    elif (cfg.max_price and p > cfg.max_price) or (cfg.min_price and p < cfg.min_price): f["price"] = 0.0; reasons.append("price outside range")
    else:
        f["price"] = 1.0
        if cfg.max_price and p <= cfg.max_price * 0.9: hi.append(f"{round((1 - p / cfg.max_price) * 100)}% under your budget")
    tl = text.lower()
    req, exc = cfg.required_keywords or [], cfg.excluded_keywords or []
    bad = [k for k in exc if (ex.get("broker") is True if k.lower() in ("תיווך", "broker") else _kw_hit(k, tl, ex))]
    if bad: f["preference"] = 0.0; reasons.append("excluded keyword present")
    else:
        got = [k for k in req if _kw_hit(k, tl, ex)]
        f["preference"] = len(got) / len(req) if req else 1.0
        if got: hi.append("Has: " + ", ".join(got))
    if ex.get("broker") is False: hi.append("No broker")
    f["quality"] = ex["confidence"]
    f["recency"] = fresh
    total = sum(w[k] * f[k] for k in f) / sum(w[k] for k in f)
    hard = f["category"] == 0 or f["price"] == 0 or (bool(cfg.location) and f["location"] == 0) or f["preference"] == 0
    if hard:
        reasons.append("hard criterion failed"); total = min(total, 0.4)
    else:
        bonus = 0.0   # small, explained "value" nudge: cheaper-than-budget and negotiable/urgent sellers (never above 100)
        if cfg.max_price and p and p <= cfg.max_price * 0.85: bonus += 0.03
        if ex.get("negotiable") or ex.get("urgent"): bonus += 0.01; hi.append("Seller seems flexible")
        total = min(1.0, total + bonus)
    s = round(total * 100)
    return {"score": s, "factors": f, "missing": missing, "rejection_reasons": reasons, "highlights": hi,
            "label": "excellent" if s >= 85 else "good" if s >= 70 else "maybe" if s >= 55 else "low"}
