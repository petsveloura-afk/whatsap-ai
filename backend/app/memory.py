"""Free per-user personalization. Pure functions here; DB wiring lives in main.py.
Adjustment is bounded (+/-10 points), explained, and only applied when enabled."""
from .neardup import embed, cosine
MAX_ADJ = 10
MAX_MEMORIES = 300

def adjustment(text: str, saved: list[list[float]], rejected: list[list[float]]) -> dict:
    if not saved and not rejected:
        return {"points": 0, "reason": "no memory yet"}
    e = embed(text)
    s = max((cosine(e, x) for x in saved), default=0.0)
    r = max((cosine(e, x) for x in rejected), default=0.0)
    delta = s - r
    pts = max(-MAX_ADJ, min(MAX_ADJ, round(delta * MAX_ADJ * 1.5))) if abs(delta) >= 0.15 else 0
    why = "similar to listings you saved" if pts > 0 else "similar to listings you rejected" if pts < 0 else "no strong similarity to past choices"
    return {"points": pts, "reason": why, "similarity_saved": round(s, 2), "similarity_rejected": round(r, 2)}
