"""Rule-based extraction (Hebrew/English). Returns confidence; unknown fields stay None."""
import re
CITIES = {"חולון": "Holon", "בת ים": "Bat Yam", "תל אביב": "Tel Aviv", "holon": "Holon", "bat yam": "Bat Yam", "tel aviv": "Tel Aviv"}
def extract(text: str) -> dict:
    t = text.lower()
    out = {"category": None, "rooms": None, "location": None, "price": None, "currency": None, "broker": None, "condition": None}
    m = re.search(r"(\d[\d,\.]*)\s*(₪|ש\"ח|ש״ח|שח|ils|nis)", t)
    if m:
        out["price"] = float(m.group(1).replace(",", "")); out["currency"] = "ILS"
    m = re.search(r"(\d(?:\.5)?)\s*חדרים|(\d(?:\.5)?)[- ]?room", t)
    if m: out["rooms"] = float(m.group(1) or m.group(2))
    for k, v in CITIES.items():
        if k in t: out["location"] = v; break
    if "דירת" in t or "דירה" in t or "apartment" in t: out["category"] = "real_estate"
    if "ללא תיווך" in t or "no broker" in t: out["broker"] = False
    elif "תיווך" in t or "broker" in t: out["broker"] = True
    if "משופצת" in t or "renovated" in t: out["condition"] = "renovated"
    found = sum(v is not None for v in out.values())
    out["confidence"] = round(found / 7, 2)
    return out
