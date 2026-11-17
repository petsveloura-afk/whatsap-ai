"""v3.16 brain+ : pure helpers (no DB, no network, no new dependency) that make the memory and the profile smarter.

What lives here
- insights(rows): learns the user's tastes from what they actually saved / contacted / bought / rejected
  (cities, categories, rooms, budget band, deal type, wanted features) with an honest confidence level.
- memory_statements(ins): turns insights into short Hebrew preference sentences the agent can remember.
  Every sentence starts with LEARNED_PREFIX so the user (and the code) can tell learned memories from typed ones.
- completeness(facts): a 0-100 profile score with concrete next steps (each pointing to a UI tab).
- recency_boost(created_at, now): a small, bounded ranking bonus so fresher memories win ties (used by agent.recall).

Design rules: additive (nothing existing is modified or removed), bounded, explainable, and never invents data:
a statement is produced only when enough real evidence exists (MIN_EVIDENCE listings that agree).
"""
import collections, datetime as dt, math, statistics

LEARNED_PREFIX = "נלמד מהפעולות שלך: "
POSITIVE = ("saved", "contacted", "purchased")
NEGATIVE = ("rejected",)
MIN_EVIDENCE = 2            # listings that must agree before a taste is stated
RECENCY_MAX = 0.04          # maximum ranking bonus for a brand-new memory (cosine scores live in 0..1)
RECENCY_HALF_LIFE_DAYS = 60.0

CAT_HE = {"real_estate": "נדל״ן", "vehicles": "רכב", "electronics": "אלקטרוניקה", "business": "עסקים", "services": "שירותים", "other": "אחר"}
DEAL_HE = {"rent": "להשכרה", "sale": "למכירה"}
FEATURE_HE = {"parking": "חניה", "elevator": "מעלית", "balcony": "מרפסת", "safe_room": "ממ״ד", "storage": "מחסן", "ac": "מיזוג", "renovated": "משופצת", "garden": "גינה"}


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


def _city_he(city):
    try:
        from .feeds import hebrew_name
        return hebrew_name(city) or city
    except Exception:
        return city


def insights(rows: list[dict]) -> dict:
    """rows: [{status, score, extracted}] (extracted may be missing). Returns the learned taste profile."""
    pos = [r for r in rows if r.get("status") in POSITIVE]
    neg = [r for r in rows if r.get("status") in NEGATIVE]
    ex = lambda r: (r.get("extracted") or {})
    cities = collections.Counter(ex(r).get("location") for r in pos if ex(r).get("location"))
    cats = collections.Counter(ex(r).get("category") for r in pos if ex(r).get("category"))
    deals = collections.Counter(ex(r).get("deal_type") for r in pos if ex(r).get("deal_type"))
    feats = collections.Counter(f for r in pos for f in (ex(r).get("features") or []) if isinstance(f, str))
    rooms = sorted(x for x in (_num(ex(r).get("rooms")) for r in pos) if x)
    prices = sorted(x for x in (_num(ex(r).get("price")) for r in pos) if x and x > 0)
    rej_cities = collections.Counter(ex(r).get("location") for r in neg if ex(r).get("location"))
    scores = [x for x in (_num(r.get("score")) for r in rows) if x is not None]
    band = None
    if len(prices) >= MIN_EVIDENCE:
        q = statistics.quantiles(prices, n=4, method="inclusive") if len(prices) >= 4 else [prices[0], statistics.median(prices), prices[-1]]
        band = {"low": q[0], "median": statistics.median(prices), "high": q[-1]}
    n = len(pos)
    return {"positive": n, "negative": len(neg), "total": len(rows),
            "confidence": "high" if n >= 10 else "medium" if n >= 4 else "low" if n >= 1 else "none",
            "cities": cities.most_common(3), "categories": cats.most_common(3), "deal_types": deals.most_common(2),
            "features": feats.most_common(4), "rooms": (rooms[0], rooms[-1]) if len(rooms) >= MIN_EVIDENCE else None,
            "price_band": band, "avoid_cities": [c for c, k in rej_cities.most_common(2) if k >= MIN_EVIDENCE and k > cities.get(c, 0)],
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None, "best_score": max(scores) if scores else None}


def memory_statements(ins: dict) -> list[str]:
    """Short Hebrew sentences (<= 200 chars) supported by at least MIN_EVIDENCE real listings. Empty when there is not enough evidence."""
    out: list[str] = []
    P = LEARNED_PREFIX
    cities = [(c, k) for c, k in ins.get("cities", []) if k >= MIN_EVIDENCE]
    if cities: out.append(P + "מעדיף אזורים: " + ", ".join(str(_city_he(c)) for c, k in cities))
    cats = [(c, k) for c, k in ins.get("categories", []) if k >= MIN_EVIDENCE]
    if cats:
        deal = next((d for d, k in ins.get("deal_types", []) if k >= MIN_EVIDENCE), None)
        out.append(P + "מתעניין ב" + ", ".join(CAT_HE.get(c, c) for c, k in cats) + (" " + DEAL_HE.get(deal, "") if deal and any(c == "real_estate" for c, _ in cats) else ""))
    if ins.get("rooms"):
        lo, hi = ins["rooms"]; out.append(P + (f"דירות של {lo:g} חדרים" if lo == hi else f"דירות של {lo:g} עד {hi:g} חדרים"))
    b = ins.get("price_band")
    if b: out.append(P + f"טווח מחיר מועדף סביב {_fmt(b['median'])} ₪ (בין {_fmt(b['low'])} ל-{_fmt(b['high'])})")
    feats = [f for f, k in ins.get("features", []) if k >= MIN_EVIDENCE]
    if feats: out.append(P + "חשוב לו: " + ", ".join(FEATURE_HE.get(f, f) for f in feats))
    if ins.get("avoid_cities"): out.append(P + "נוטה לפסול מודעות מ: " + ", ".join(str(_city_he(c)) for c in ins["avoid_cities"]))
    return [s[:200] for s in out]


def completeness(f: dict) -> dict:
    """f: booleans/ints describing the account. Returns {score, level, tips:[{id,text,tab,points}]} - tips only for what is still missing."""
    steps = [
        ("search", 25, bool(f.get("searches")), "צור חיפוש ראשון: מה מחפשים, באיזה אזור ובאיזה תקציב.", "discover"),
        ("listings", 20, bool(f.get("listings")), "הבא או הדבק מודעות כדי שהמערכת תדרג אותן.", "discover"),
        ("feedback", 20, f.get("saved", 0) + f.get("rejected", 0) >= 3, "שמור או דחה לפחות שלוש מודעות. כך המערכת לומדת מה מתאים לך.", "opps"),
        ("memory", 15, bool(f.get("memories")) and bool(f.get("personalization", True)), "אמור לסוכן מה חשוב לך, או הפעל סנכרון זיכרון בפרופיל.", "agent"),
        ("contact", 10, bool(f.get("whatsapp_consent") or f.get("telegram")), "חבר וואטסאפ להתראות, או ערוץ טלגרם כמקור מודעות, כדי לא לפספס הזדמנות.", "account"),
        ("privacy", 10, bool(f.get("personalization", True)), "הפעל התאמה אישית כדי שהציונים יתאימו אליך.", "account"),
    ]
    score = sum(p for _, p, ok, _, _ in steps if ok)
    return {"score": score, "level": "מצוין" if score >= 90 else "טוב" if score >= 60 else "בהתחלה",
            "tips": [{"id": i, "text": t, "tab": tab, "points": p} for i, p, ok, t, tab in steps if not ok]}


def _aware(t):
    if t is None: return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def recency_boost(created_at, now: dt.datetime | None = None) -> float:
    """0..RECENCY_MAX, halves every RECENCY_HALF_LIFE_DAYS. Unknown dates get 0 (never an error)."""
    try:
        t = _aware(created_at)
        if t is None: return 0.0
        age = max(0.0, ((_aware(now) or dt.datetime.now(dt.timezone.utc)) - t).total_seconds() / 86400)
        return RECENCY_MAX * 0.5 ** (age / RECENCY_HALF_LIFE_DAYS)
    except Exception:
        return 0.0


def initials(email: str) -> str:
    """Two-letter avatar text from an e-mail local part (works for Hebrew and Latin)."""
    local = (email or "?").split("@")[0]
    parts = [p for p in "".join(c if c.isalnum() else " " for c in local).split() if p]
    if not parts: return "?"
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else (parts[0][1] if len(parts[0]) > 1 else ""))).upper()
