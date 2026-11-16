"""Free, rule-based natural-language -> search parameters (Hebrew/English). No external API, no cost.
Returns params, clarifying questions for anything required that could not be determined, and an
`understood` list so the UI can show the user what the system understood. `params` keys are unchanged."""
import re
from .extract import _norm, extract, find_cities, detect_category, parse_number, _MULT, _CURW, _MULTW

_N = r"(\d[\d,\.]*\d|\d)"
_TAIL = r"\s*(" + _MULTW + r"\b)?\s*(" + _CURW + r")?"
_MAX = re.compile(r"(?:עד|מקסימום|מקס'?|לא יותר מ|מתחת\s*(?:ל)?|פחות מ|זול מ|תקציב(?:\s*של)?|up to|max(?:imum)?|under|below|budget(?: of)?)\s*(?:של\s*)?" + _N + _TAIL, re.I)
_MIN = re.compile(r"(?:מינימום|לפחות|מעל|החל מ|from|at least|min(?:imum)?|above|over)\s*" + _N + _TAIL, re.I)
_BETWEEN = re.compile(r"(?:בין|between)\s*" + _N + r"\s*(" + _MULTW + r"\b)?\s*(?:ל|ל-|ו|to|and|-)\s*" + _N + _TAIL, re.I)
_CATS = {
    "real_estate": ("דירה", "דירת", "בית", "apartment", "house", "flat", "שכירות", "rent", "פנטהאוז", "דופלקס", "סטודיו", "villa"),
    "vehicles": ("רכב", "אוטו", "car", "vehicle", "אופנוע", "motorcycle", "קטנוע", "מכונית"),
    "electronics": ("טלפון", "אייפון", "iphone", "מחשב", "laptop", "טלוויזיה", "tv", "electronics", "אלקטרוניקה", "אייפד", "סמסונג"),
}
_FEAT_KW = {"parking": "חניה", "elevator": "מעלית", "balcony": "מרפסת", "safe_room": "ממד", "storage": "מחסן", "ac": "מזגן", "garden": "גינה", "furnished": "מרוהטת"}

def _val(num, mult, cur):
    v = parse_number(num) * _MULT.get((mult or "").lower(), 1)
    return v if (cur or mult or v >= 300) else None     # a bare small number is rooms/floor, not a price

def parse_search(text: str) -> dict:
    t = text.strip(); tl = _norm(t)
    p = {"name": None, "category": None, "location": None, "locations": [], "min_price": None,
         "max_price": None, "required_keywords": [], "excluded_keywords": [], "min_score": 60}
    p["locations"] = find_cities(t)
    if p["locations"]: p["location"] = p["locations"][0]
    m = _BETWEEN.search(tl)
    if m:
        a, b = _val(m.group(1), m.group(2) or m.group(4), m.group(5)), _val(m.group(3), m.group(4), m.group(5))
        if a and b: p["min_price"], p["max_price"] = min(a, b), max(a, b)
    if p["max_price"] is None:
        m = _MAX.search(tl)
        if m: p["max_price"] = _val(m.group(1), m.group(2), m.group(3))
    if p["min_price"] is None:
        m = _MIN.search(tl)
        if m: p["min_price"] = _val(m.group(1), m.group(2), m.group(3))
    ex = extract(t)
    p["category"] = detect_category(t) or ex.get("category")
    if not p["category"]:
        for cat, words in _CATS.items():
            if any(w in tl for w in words): p["category"] = cat; break
    if ex.get("rooms") is not None:
        r = ex["rooms"]; p["required_keywords"].append(str(int(r)) if r == int(r) else str(r))
    if ex.get("condition") == "renovated": p["required_keywords"].append("משופצת")
    if re.search(r"(?:עם|with|שיש)\s+", tl):
        for f in ex.get("features") or []:
            if f in _FEAT_KW and _FEAT_KW[f] not in p["required_keywords"]: p["required_keywords"].append(_FEAT_KW[f])
    if ex.get("broker") is False: p["excluded_keywords"].append("תיווך")
    parts = [x for x in (p["category"], p["location"]) if x]
    p["name"] = " · ".join(parts) or t[:60]
    q = []
    if not p["category"]: q.append("איזה סוג הזדמנות אתה מחפש (נדל\"ן, רכב, אלקטרוניקה)?")
    if p["max_price"] is None: q.append("מה התקציב המקסימלי?")
    u = []
    if p["category"]: u.append("קטגוריה: " + p["category"])
    if p["locations"]: u.append("אזור: " + ", ".join(p["locations"]))
    if p["min_price"] or p["max_price"]: u.append("תקציב: " + (f"{p['min_price']:,.0f} – {p['max_price']:,.0f}" if p["min_price"] and p["max_price"] else f"עד {p['max_price']:,.0f}" if p["max_price"] else f"מ-{p['min_price']:,.0f}"))
    if p["required_keywords"]: u.append("חובה: " + ", ".join(p["required_keywords"]))
    if p["excluded_keywords"]: u.append("בלי: " + ", ".join(p["excluded_keywords"]))
    return {"params": p, "clarifications": q, "understood": u}
