"""OPTIONAL LLM extraction (OpenAI-compatible). Off by default: needs OPENAI_API_KEY (paid) AND the admin flag
`llm_extraction`. Only the listing text is sent. The model output is validated and may only FILL fields the
rule-based extractor left empty; any error falls back silently to rules."""
import json, logging, os
log = logging.getLogger("sniper")
CATS = {"real_estate", "vehicles", "electronics", "business", "services", "other"}

def configured() -> bool: return bool(os.environ.get("OPENAI_API_KEY"))

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

def enhance(text: str, rule: dict, post=None) -> dict:
    """post(url, headers, json)->dict is injectable for tests."""
    try:
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        body = {"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text[:4000]}]}
        hdr = {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
        if post is None:
            import httpx
            post = lambda u, h, j: httpx.post(u, headers=h, json=j, timeout=20).json()
        resp = post(base + "/chat/completions", hdr, body)
        return merge(rule, json.loads(resp["choices"][0]["message"]["content"]))
    except Exception as e:
        log.warning("llm extraction failed: %s", type(e).__name__); return rule
