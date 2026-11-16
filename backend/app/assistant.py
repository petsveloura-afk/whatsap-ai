"""Free rule-based assistant over the user's own listings (Hebrew/English). Pure functions: rows are plain dicts
{id, score, status, extracted, risks, detail, url}. Optional LLM polishing happens in routes_v4 only if configured."""
import statistics, re
from .extract import find_cities, _norm

def _price(r): return (r.get("extracted") or {}).get("price")
def _fmt(r) -> str:
    ex = r.get("extracted") or {}; p = ex.get("price")
    bits = [f"{r.get('score', 0)}%", ex.get("location") or "מיקום לא ידוע"]
    if ex.get("rooms") is not None: bits.append(f"{ex['rooms']:g} חדרים")
    if ex.get("brand"): bits.append(ex["brand"] + (" " + ex["model"] if ex.get("model") else ""))
    if p: bits.append(f"{p:,.0f} {'₪' if (ex.get('currency') or 'ILS') == 'ILS' else ex.get('currency')}")
    return " · ".join(bits)

def explain(r: dict) -> str:
    d = r.get("detail") or {}; lines = [f"ציון {r.get('score', 0)}% ({d.get('label', '')})".strip()]
    if d.get("highlights"): lines.append("למה זה מתאים: " + "; ".join(d["highlights"]))
    if d.get("missing"): lines.append("מידע חסר במודעה: " + ", ".join(d["missing"]))
    if d.get("rejection_reasons"): lines.append("למה נפסל: " + ", ".join(d["rejection_reasons"]))
    if r.get("risks"): lines.append("שים לב: " + "; ".join(r["risks"]))
    if len(lines) == 1: lines.append("אין הערות מיוחדות.")
    return "\n".join(lines)

def report(rows: list[dict]) -> dict:
    prices = [p for p in (_price(r) for r in rows) if p]
    cities: dict[str, int] = {}
    for r in rows:
        c = (r.get("extracted") or {}).get("location")
        if c: cities[c] = cities.get(c, 0) + 1
    top = sorted((r for r in rows if r.get("status") == "new"), key=lambda r: -r.get("score", 0))[:5]
    return {"total": len(rows), "new": sum(r.get("status") == "new" for r in rows), "rejected": sum(r.get("status") == "rejected" for r in rows),
            "avg_score": round(statistics.fmean([r.get("score", 0) for r in rows])) if rows else 0,
            "price": {"min": min(prices), "median": round(statistics.median(prices)), "max": max(prices)} if prices else None,
            "cities": dict(sorted(cities.items(), key=lambda x: -x[1])[:8]), "top_ids": [r["id"] for r in top]}

def answer(question: str, rows: list[dict]) -> dict:
    q = _norm(question); cities = find_cities(question)
    pool = [r for r in rows if not cities or (r.get("extracted") or {}).get("location") in cities]
    if re.search(r"ללא תיווך|בלי תיווך|no broker", q): pool = [r for r in pool if (r.get("extracted") or {}).get("broker") is False]
    live = [r for r in pool if r.get("status") == "new"]
    where = (" ב-" + ", ".join(cities)) if cities else ""
    def pick(items, title, n=3):
        if not items: return {"answer": "לא מצאתי הזדמנויות מתאימות" + where + ". נסה להוסיף מקורות או להרחיב את החיפוש.", "listing_ids": [], "intent": title}
        return {"answer": f"{title}{where}:\n" + "\n".join(f"{i + 1}. {_fmt(r)}" for i, r in enumerate(items[:n])), "listing_ids": [r["id"] for r in items[:n]], "intent": title}
    if re.search(r"זול|cheap|lowest", q): return pick(sorted([r for r in live if _price(r)], key=_price), "הכי זולות")
    if re.search(r"יקר|expensive|highest price", q): return pick(sorted([r for r in live if _price(r)], key=lambda r: -_price(r)), "הכי יקרות")
    if re.search(r"נפסל|נדחה|למה|rejected|why", q):
        rej = [r for r in pool if r.get("status") == "rejected"]
        reasons: dict[str, int] = {}
        for r in rej:
            for x in (r.get("detail") or {}).get("rejection_reasons", []): reasons[x] = reasons.get(x, 0) + 1
        txt = "; ".join(f"{k} ({v})" for k, v in sorted(reasons.items(), key=lambda x: -x[1])) or "אין סיבות רשומות"
        return {"answer": f"{len(rej)} מודעות נפסלו{where}. סיבות עיקריות: {txt}", "listing_ids": [r["id"] for r in rej[:5]], "intent": "rejected"}
    if re.search(r"סיכון|חשוד|הונאה|אזהרה|אזהרות|warning|scam|risk|suspicious", q): return pick([r for r in pool if r.get("risks")], "מודעות עם סימני אזהרה")
    if re.search(r"כמה|count|how many", q): return {"answer": f"יש {len(live)} הזדמנויות פעילות{where} (מתוך {len(pool)} מודעות שנותחו).", "listing_ids": [], "intent": "count"}
    if re.search(r"ממוצע|חציון|average|median|סיכום|summary|דוח", q):
        rp = report(pool); pr = rp["price"]
        return {"answer": f"{rp['total']} מודעות, ציון ממוצע {rp['avg_score']}%." + (f" מחיר חציוני {pr['median']:,.0f} (בין {pr['min']:,.0f} ל-{pr['max']:,.0f})." if pr else ""), "listing_ids": rp["top_ids"], "intent": "report"}
    if live: return pick(sorted(live, key=lambda r: -r.get("score", 0)), "ההזדמנויות הטובות ביותר")
    return {"answer": "אפשר לשאול: מה הכי זול? מה הכי מתאים בחולון? למה נפסלו מודעות? יש סימני אזהרה? תן סיכום. עדיין אין הזדמנויות פעילות.", "listing_ids": [], "intent": "help"}
