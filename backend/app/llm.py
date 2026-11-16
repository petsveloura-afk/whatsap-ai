"""OPTIONAL LLM extraction (OpenAI-compatible). Off by default: needs OPENAI_API_KEY (paid) AND the admin flag
`llm_extraction`. Only the listing text is sent. The model output is validated and may only FILL fields the
rule-based extractor left empty; any error falls back silently to rules."""
import json, logging, os
log = logging.getLogger("sniper")
CATS = {"real_estate", "vehicles", "electronics", "business", "services", "other"}

# Providers with a FREE tier (you create a free API key yourself; nothing is paid by default). All speak the OpenAI-compatible protocol.
PRESETS = {"openai": ("https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
           "groq": ("https://api.groq.com/openai/v1", "llama-3.1-8b-instant", "GROQ_API_KEY"),
           "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash", "GEMINI_API_KEY"),
           "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.1-8b-instruct:free", "OPENROUTER_API_KEY"),
           "ollama": ("http://localhost:11434/v1", "llama3.1", "OLLAMA_API_KEY")}   # self-hosted, no key needed (set LLM_PROVIDER=ollama)

def _cfg():
    """-> (base_url, model, api_key) or None. LLM_PROVIDER picks a preset; otherwise the first provider whose key is set (openai first)."""
    name = os.environ.get("LLM_PROVIDER", "").lower()
    names = [name] if name in PRESETS else [n for n in PRESETS if os.environ.get(PRESETS[n][2])]
    for n in names:
        base, model, keyvar = PRESETS[n]; key = os.environ.get(keyvar) or os.environ.get("LLM_API_KEY") or ("ollama" if n == "ollama" else "")
        if not key: continue
        base = os.environ.get("OPENAI_BASE_URL", base) if n == "openai" else os.environ.get("LLM_BASE_URL", base)
        return base.rstrip("/"), os.environ.get("LLM_MODEL", model), key
    return None

def configured() -> bool: return _cfg() is not None

def chat(system: str, user: str, post=None, max_chars: int = 4000):
    """Optional free-text helper for the assistant. Returns text or None (never raises)."""
    c = _cfg()
    if not c: return None
    try:
        base, model, key = c
        body = {"model": model, "temperature": 0.2, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user[:max_chars]}]}
        if post is None:
            import httpx
            post = lambda u, h, j: httpx.post(u, headers=h, json=j, timeout=25).json()
        return post(base + "/chat/completions", {"Authorization": "Bearer " + key}, body)["choices"][0]["message"]["content"].strip()
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

def enhance(text: str, rule: dict, post=None) -> dict:
    """post(url, headers, json)->dict is injectable for tests."""
    try:
        base, model, key = _cfg()
        body = {"model": model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text[:4000]}]}
        hdr = {"Authorization": "Bearer " + key}
        if post is None:
            import httpx
            post = lambda u, h, j: httpx.post(u, headers=h, json=j, timeout=20).json()
        resp = post(base + "/chat/completions", hdr, body)
        return merge(rule, json.loads(resp["choices"][0]["message"]["content"]))
    except Exception as e:
        log.warning("llm extraction failed: %s", type(e).__name__); return rule
