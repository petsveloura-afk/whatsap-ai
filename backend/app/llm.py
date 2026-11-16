"""LLM helpers (extraction + short assistant text) on top of brains.py, the free multi-provider router.
Off by default: needs at least one free key (see brains.py) AND the admin flag `llm_extraction`. Only the listing text is sent.
The model output is validated and may only FILL fields the rule-based extractor left empty; any error falls back silently to rules.
Failover between keys/models/providers is handled by brains.complete, so one exhausted free key never breaks anything."""
import logging
from . import brains
log = logging.getLogger("sniper")
CATS = {"real_estate", "vehicles", "electronics", "business", "services", "other"}


def _cfg():
    """Legacy accessor -> (base_url, model, api_key) of the first provider the router would use, or None."""
    p = brains.primary()
    return (p["base"], p["model"], p["key"]) if p else None


def configured() -> bool: return brains.configured()


def chat(system: str, user: str, post=None, max_chars: int = 4000):
    """Optional free-text helper for the assistant. Returns text or None (never raises)."""
    if not brains.configured(): return None
    try:
        r = brains.complete([{"role": "system", "content": system}, {"role": "user", "content": user[:max_chars]}], purpose="chat", post=post, timeout=25)
        return brains.text_of(r) or None
    except Exception as e:
        log.warning("llm chat failed: %s", type(e).__name__); return None


def validate(d: dict) -> dict:
    out = {}
    if not isinstance(d, dict): return out
    if d.get("category") in CATS: out["category"] = d["category"]
    for k in ("location", "condition", "currency"):
        if isinstance(d.get(k), str) and d[k].strip(): out[k] = d[k].strip()[:60]
    if isinstance(d.get("rooms"), (int, float)) and not isinstance(d["rooms"], bool) and 0 < d["rooms"] <= 20: out["rooms"] = float(d["rooms"])
    if isinstance(d.get("price"), (int, float)) and not isinstance(d["price"], bool) and 0 < d["price"] < 1e10: out["price"] = float(d["price"])
    if isinstance(d.get("broker"), bool): out["broker"] = d["broker"]
    return out

def merge(rule: dict, llm: dict) -> dict:
    out = dict(rule)
    for k, v in validate(llm).items():
        if out.get(k) is None: out[k] = v
    keys = ("category", "rooms", "location", "price", "currency", "broker", "condition")
    out["confidence"] = round(sum(out.get(k) is not None for k in keys) / 7, 2)
    out["extraction"] = "rules+llm"
    return out

PROMPT = ("Extract fields from the classified listing. Reply with ONLY a JSON object with keys: category "
          "(real_estate|vehicles|electronics|business|services|other), rooms (number|null), location (English city name|null), "
          "price (number|null), currency (ISO code|null), broker (true|false|null), condition (string|null). Never invent values.")

_KEYS = ("category", "rooms", "location", "price", "currency", "broker", "condition")


def enhance(text: str, rule: dict, post=None) -> dict:
    """post(url, headers, json)->dict is injectable for tests. Skips the model entirely when the rules found every field (saves free quota)."""
    if all(rule.get(k) is not None for k in _KEYS): return rule
    try:
        r = brains.complete([{"role": "system", "content": PROMPT}, {"role": "user", "content": text[:4000]}], temperature=0, json_mode=True,
                            purpose="extract", post=post, timeout=20, cache=True)
        return merge(rule, brains.parse_json(brains.text_of(r)))
    except Exception as e:
        log.warning("llm extraction failed: %s", type(e).__name__); return rule
