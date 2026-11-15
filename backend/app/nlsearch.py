"""Free, rule-based natural-language -> search parameters (Hebrew/English).
No external API, no cost. Returns params plus a list of clarifying questions
for anything required that could not be determined."""
import re
from .extract import CITIES

_NUM = r"(\d[\d,\.]*)"
_MAX = re.compile(r"(?:עד|מקסימום|מקס'?|עד\s+ל|up to|max(?:imum)?|under|below)\s*(?:של\s*)?" + _NUM + r"\s*(?:₪|ש\"ח|ש״ח|שח|ils|nis)?", re.I)
_MIN = re.compile(r"(?:מינימום|לפחות|מ-?|from|at least|min(?:imum)?)\s*" + _NUM + r"\s*(?:₪|ש\"ח|ש״ח|שח|ils|nis)", re.I)
_CATS = {
    "real_estate": ("דירה", "דירת", "בית", "apartment", "house", "flat", "שכירות", "rent"),
    "vehicles": ("רכב", "אוטו", "car", "vehicle", "אופנוע", "motorcycle"),
    "electronics": ("טלפון", "אייפון", "iphone", "מחשב", "laptop", "טלוויזיה", "tv", "electronics", "אלקטרוניקה"),
}

def _num(s: str) -> float:
    return float(s.replace(",", ""))

def parse_search(text: str) -> dict:
    t = text.strip()
    tl = t.lower()
    p = {"name": None, "category": None, "location": None, "locations": [], "min_price": None,
         "max_price": None, "required_keywords": [], "excluded_keywords": [], "min_score": 60}
    for k, v in CITIES.items():
        if k in tl and v not in p["locations"]:
            p["locations"].append(v)
    if p["locations"]:
        p["location"] = p["locations"][0]
    m = _MAX.search(tl)
    if m:
        p["max_price"] = _num(m.group(1))
    m = _MIN.search(tl)
    if m:
        p["min_price"] = _num(m.group(1))
    for cat, words in _CATS.items():
        if any(w in tl for w in words):
            p["category"] = cat
            break
    rooms = re.search(r"(\d(?:\.5)?)\s*(?:חדרים|rooms?)", tl)
    if rooms:
        p["required_keywords"].append(rooms.group(1))
    if "משופצת" in tl or "renovated" in tl:
        p["required_keywords"].append("משופצת")
    if "ללא תיווך" in tl or "no broker" in tl or "without broker" in tl:
        p["excluded_keywords"].append("תיווך")
    parts = [x for x in (p["category"], p["location"]) if x]
    p["name"] = " · ".join(parts) or t[:60]
    q = []
    if not p["category"]:
        q.append("איזה סוג הזדמנות אתה מחפש (נדל\"ן, רכב, אלקטרוניקה)?")
    if p["max_price"] is None:
        q.append("מה התקציב המקסימלי?")
    return {"params": p, "clarifications": q}
