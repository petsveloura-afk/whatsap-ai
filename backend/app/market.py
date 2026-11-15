"""Market intelligence ("the brain"): free, local, explainable. Pure functions - DB wiring lives in routes_v3.
Gives every listing a deal verdict relative to comparable listings, and a price trend."""
import statistics, datetime as dt
MIN_SAMPLE = 5   # below this we refuse to claim a "market" (and refuse to expose pooled stats: k-anonymity)

def _q(sorted_vals, q):
    if len(sorted_vals) == 1: return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q; lo = int(pos); hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)

def summarize(prices: list[float]) -> dict:
    p = sorted(x for x in prices if x and x > 0)
    if len(p) < MIN_SAMPLE: return {"n": len(p), "enough_data": False}
    return {"n": len(p), "enough_data": True, "median": round(statistics.median(p)), "p25": round(_q(p, .25)), "p75": round(_q(p, .75)),
            "min": round(p[0]), "max": round(p[-1]), "mean": round(statistics.fmean(p))}

def deal_insight(price: float | None, prices: list[float]) -> dict:
    """Verdict is an indicator, never proof. Explains itself and says when data is insufficient."""
    st = summarize(prices)
    if price is None: return {"verdict": "unknown", "reason": "listing has no price", "market": st}
    if not st["enough_data"]: return {"verdict": "unknown", "reason": f"need at least {MIN_SAMPLE} comparable listings (have {st['n']})", "market": st}
    gap = (price - st["median"]) / st["median"]; pct = round(gap * 100)
    if gap <= -0.30: v, why = "suspicious_low", f"{abs(pct)}% below median - verify authenticity before acting (indicator only)"
    elif gap <= -0.08: v, why = "good_deal", f"{abs(pct)}% below the median of {st['n']} comparable listings"
    elif gap < 0.08: v, why = "fair", "within 8% of the median"
    else: v, why = "above_market", f"{pct}% above the median"
    return {"verdict": v, "reason": why, "gap_pct": pct, "market": st}

def weekly_trend(points: list[tuple[dt.datetime, float]]) -> list[dict]:
    buckets: dict[str, list[float]] = {}
    for t, p in points:
        y, w, _ = t.isocalendar(); buckets.setdefault(f"{y}-W{w:02d}", []).append(p)
    return [{"week": k, "median": round(statistics.median(v)), "n": len(v)} for k, v in sorted(buckets.items())]

def comparable(ex: dict, rows: list[dict]) -> list[float]:
    """rows: [{category, location, rooms, price}]; same category+location, rooms within 0.5 when both known."""
    out = []
    for r in rows:
        if r.get("price") is None or r.get("category") != ex.get("category"): continue
        if ex.get("location") and r.get("location") and r["location"] != ex["location"]: continue
        if ex.get("rooms") and r.get("rooms") and abs(r["rooms"] - ex["rooms"]) > 0.5: continue
        out.append(r["price"])
    return out
