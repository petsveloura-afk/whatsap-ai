DEFAULT_W = {"category": 25, "location": 20, "price": 25, "preference": 15, "quality": 10, "recency": 5}
def risks(ex: dict, s_cfg) -> list[str]:
    r = []
    if ex["price"] is None: r.append("Price missing")
    elif s_cfg.max_price and ex["price"] < s_cfg.max_price * 0.3: r.append("Price far below budget – verify authenticity (indicator only, not proof)")
    if ex["confidence"] < 0.4: r.append("Little structured information extracted")
    return r
def score(ex: dict, cfg, text: str, fresh: float = 1.0) -> dict:
    w = {**DEFAULT_W, **(cfg.weights or {})}
    f, missing, reasons = {}, [], []
    f["category"] = 1.0 if ex["category"] == cfg.category else (0.3 if ex["category"] is None else 0.0)
    if ex["category"] is None: missing.append("category")
    if not cfg.location: f["location"] = 1.0
    elif ex["location"] is None: f["location"] = 0.3; missing.append("location")
    else: f["location"] = 1.0 if cfg.location.lower() in ex["location"].lower() else 0.0
    p = ex["price"]
    if p is None: f["price"] = 0.3; missing.append("price")
    elif (cfg.max_price and p > cfg.max_price) or (cfg.min_price and p < cfg.min_price): f["price"] = 0.0; reasons.append("price outside range")
    else: f["price"] = 1.0
    tl = text.lower()
    req, exc = cfg.required_keywords or [], cfg.excluded_keywords or []
    if any(k.lower() in tl for k in exc): f["preference"] = 0.0; reasons.append("excluded keyword present")
    else: f["preference"] = sum(k.lower() in tl for k in req) / len(req) if req else 1.0
    f["quality"] = ex["confidence"]
    f["recency"] = fresh
    total = sum(w[k] * f[k] for k in f) / sum(w[k] for k in f)
    hard = f["category"] == 0 or f["price"] == 0 or (bool(cfg.location) and f["location"] == 0) or f["preference"] == 0
    if hard:
        reasons.append("hard criterion failed"); total = min(total, 0.4)
    return {"score": round(total * 100), "factors": f, "missing": missing, "rejection_reasons": reasons}
