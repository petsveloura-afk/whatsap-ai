"""Brains (v3.7): ONE call site for every language model, backed by many FREE providers.

Why: a single free key runs out (rate limit / daily quota) or a provider changes its model names. Here every request is tried on
the next available key / model / provider automatically, so the assistant keeps answering. All providers speak the OpenAI-compatible
chat protocol, so one small client covers them.

Free-only guarantee
* Paid providers (OpenAI) are never used unless you set LLM_PROVIDER=openai or BRAINS_ALLOW_PAID=1 explicitly.
* The extraction purpose has a daily cap (BRAINS_EXTRACT_DAILY, default 400 calls) so bulk imports cannot eat the quota the assistant needs.
* Identical extraction prompts are served from a small in-memory cache (no repeated calls).

Environment (all optional; set only what you have)
  GEMINI_API_KEY GROQ_API_KEY CEREBRAS_API_KEY OPENROUTER_API_KEY MISTRAL_API_KEY SAMBANOVA_API_KEY NVIDIA_API_KEY
  GITHUB_MODELS_TOKEN HF_TOKEN CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID, OLLAMA_BASE_URL (self-hosted)
  CUSTOM_LLM_BASE_URL + CUSTOM_LLM_KEY (+ CUSTOM_LLM_MODEL): any other OpenAI-compatible endpoint
  Every key variable accepts several keys: KEY=k1,k2,k3 or KEY_2, KEY_3 ... (more keys = more free quota).
  <NAME>_MODEL=model1,model2   override the model list of one provider (names change; this is the escape hatch).
  LLM_PROVIDER=groq            try this provider first (others remain as fallback).
  BRAINS_KEYLESS=1             also allow the key-less community endpoint (OVHcloud). Off by default: it sends text to a third party.
Only the text needed for the task is ever sent. Keys never appear in logs, status or error messages.
"""
import hashlib, json, logging, os, re, threading, time
from . import pool

log = logging.getLogger("sniper")
# tier: "smart" = best quality (agent, tool calling) / "fast" = cheap + quick (extraction, short polishing)
S, F = "smart", "fast"
_CF_BASE = lambda: ("https://api.cloudflare.com/client/v4/accounts/%s/ai/v1" % os.environ["CLOUDFLARE_ACCOUNT_ID"]) if os.environ.get("CLOUDFLARE_ACCOUNT_ID") else None

# Priority order = default try order. Model ids change over time: each provider lists several, and a "model not found" answer
# simply moves on to the next one (and the bad one is skipped for an hour). Override any list with <NAME>_MODEL.
PROVIDERS: list[dict] = [
    {"name": "gemini", "label": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
     "models": [("gemini-2.5-flash", True, S), ("gemini-2.5-flash-lite", True, F), ("gemini-2.0-flash", True, F)], "json": True,
     "url": "https://aistudio.google.com/apikey", "note": "חינם, בלי כרטיס אשראי. הכי טוב לעברית ולהקשר ארוך."},
    {"name": "groq", "label": "Groq", "base": "https://api.groq.com/openai/v1", "env": ("GROQ_API_KEY",),
     "models": [("llama-3.3-70b-versatile", True, S), ("openai/gpt-oss-120b", True, S), ("llama-3.1-8b-instant", False, F), ("openai/gpt-oss-20b", True, F)], "json": True,
     "url": "https://console.groq.com/keys", "note": "חינם, בלי כרטיס. מהיר מאוד."},
    {"name": "cerebras", "label": "Cerebras", "base": "https://api.cerebras.ai/v1", "env": ("CEREBRAS_API_KEY",),
     "models": [("gpt-oss-120b", True, S), ("llama-3.3-70b", True, S), ("qwen-3-32b", True, S), ("llama3.1-8b", False, F)], "json": True,
     "url": "https://cloud.cerebras.ai", "note": "חינם, מכסה יומית גדולה. הקשר קצר יחסית."},
    {"name": "openrouter", "label": "OpenRouter (:free)", "base": "https://openrouter.ai/api/v1", "env": ("OPENROUTER_API_KEY",),
     "models": [("meta-llama/llama-3.3-70b-instruct:free", True, S), ("openai/gpt-oss-120b:free", True, S), ("mistralai/mistral-small-3.2-24b-instruct:free", True, F),
                ("google/gemma-3-27b-it:free", False, F)], "json": False,
     "url": "https://openrouter.ai/keys", "note": "חינם: מודלים עם סיומת :free. מכסה יומית קטנה, מצוין כגיבוי."},
    {"name": "mistral", "label": "Mistral", "base": "https://api.mistral.ai/v1", "env": ("MISTRAL_API_KEY",),
     "models": [("mistral-small-latest", True, S), ("open-mistral-nemo", True, F)], "json": True,
     "url": "https://console.mistral.ai/api-keys", "note": "שכבת Experiment חינמית (דורשת אימות טלפון)."},
    {"name": "github", "label": "GitHub Models", "base": "https://models.github.ai/inference", "env": ("GITHUB_MODELS_TOKEN",),
     "models": [("openai/gpt-4.1-mini", True, S), ("openai/gpt-4o-mini", True, F), ("meta/Llama-3.3-70B-Instruct", True, S)], "json": True,
     "url": "https://github.com/settings/personal-access-tokens", "note": "חינם עם חשבון GitHub: צור טוקן עם הרשאת models:read."},
    {"name": "sambanova", "label": "SambaNova", "base": "https://api.sambanova.ai/v1", "env": ("SAMBANOVA_API_KEY",),
     "models": [("Meta-Llama-3.3-70B-Instruct", True, S), ("Meta-Llama-3.1-8B-Instruct", False, F)], "json": False,
     "url": "https://cloud.sambanova.ai/apis", "note": "שכבה חינמית עם מגבלות קצב."},
    {"name": "nvidia", "label": "NVIDIA NIM", "base": "https://integrate.api.nvidia.com/v1", "env": ("NVIDIA_API_KEY",),
     "models": [("meta/llama-3.3-70b-instruct", True, S), ("meta/llama-3.1-8b-instruct", False, F)], "json": False,
     "url": "https://build.nvidia.com", "note": "קרדיטים חינמיים למפתחים (מכסה מוגבלת)."},
    {"name": "huggingface", "label": "Hugging Face", "base": "https://router.huggingface.co/v1", "env": ("HF_TOKEN", "HUGGINGFACE_API_KEY"),
     "models": [("meta-llama/Llama-3.3-70B-Instruct", True, S), ("Qwen/Qwen2.5-72B-Instruct", True, S)], "json": False,
     "url": "https://huggingface.co/settings/tokens", "note": "קרדיט חינמי חודשי קטן."},
    {"name": "cloudflare", "label": "Cloudflare Workers AI", "base": _CF_BASE, "env": ("CLOUDFLARE_API_TOKEN",),
     "models": [("@cf/meta/llama-3.3-70b-instruct-fp8-fast", True, S), ("@cf/meta/llama-3.1-8b-instruct", False, F)], "json": False,
     "url": "https://dash.cloudflare.com/profile/api-tokens", "note": "חינם עד מכסה יומית. צריך גם CLOUDFLARE_ACCOUNT_ID."},
    {"name": "custom", "label": "מותאם אישית (OpenAI-compatible)", "base": lambda: os.environ.get("CUSTOM_LLM_BASE_URL"), "env": ("CUSTOM_LLM_KEY",),
     "models": [("default", True, S)], "model_env": "CUSTOM_LLM_MODEL", "json": False, "url": "", "note": "כל שרת תואם OpenAI: LM Studio, vLLM, LiteLLM, שער חינמי אחר."},
    {"name": "ollama", "label": "Ollama (אצלך)", "base": lambda: os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1", "env": ("OLLAMA_API_KEY",),
     "models": [("llama3.1", True, S)], "json": True, "url": "https://ollama.com", "note": "רץ על המחשב/שרת שלך, בלי מגבלות ובלי עלות.", "implicit_key": "ollama"},
    {"name": "ovh", "label": "OVHcloud (בלי מפתח)", "base": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", "env": ("OVH_API_KEY",),
     "models": [("Meta-Llama-3_3-70B-Instruct", True, S)], "json": False, "url": "https://endpoints.ai.cloud.ovh.net", "note": "ללא מפתח, מוגבל בקצב. מופעל רק עם BRAINS_KEYLESS=1.", "keyless": True},
    {"name": "openai", "label": "OpenAI (בתשלום)", "base": "https://api.openai.com/v1", "env": ("OPENAI_API_KEY",),
     "models": [("gpt-4o-mini", True, F)], "json": True, "url": "https://platform.openai.com/api-keys", "note": "בתשלום. לא נכלל אלא אם הוגדר LLM_PROVIDER=openai או BRAINS_ALLOW_PAID=1.", "paid": True},
]
BY_NAME = {p["name"]: p for p in PROVIDERS}
MAX_ATTEMPTS = 10
_DAILY_CAPS = {"extract": int(os.environ.get("BRAINS_EXTRACT_DAILY", "400") or 400)}
_used: dict[str, list] = {}           # purpose -> [day, count]
_cache: dict[str, tuple] = {}         # key -> (expires, text)
_lock = threading.Lock()


class BrainsUnavailable(Exception):
    pass


# ------------------------------------------------------------------ configuration
def _pinned() -> str:
    return (os.environ.get("LLM_PROVIDER") or "").lower()


def _paid_ok(p: dict) -> bool:
    return not p.get("paid") or _pinned() == p["name"] or os.environ.get("BRAINS_ALLOW_PAID") == "1"


def _keys(p: dict) -> list[str]:
    ks = pool.keys(*p["env"])
    if not ks and _pinned() == p["name"]:
        ks = pool.keys("LLM_API_KEY")                                   # legacy generic key for the pinned provider
    if not ks and p.get("implicit_key") and (_pinned() == p["name"] or os.environ.get("OLLAMA_BASE_URL")): ks = [p["implicit_key"]]
    if not ks and p.get("keyless") and (os.environ.get("BRAINS_KEYLESS") == "1" or _pinned() == p["name"]): ks = ["anonymous"]
    return ks


def _base(p: dict) -> str | None:
    b = p["base"]() if callable(p["base"]) else p["base"]
    if _pinned() == p["name"] and os.environ.get("OPENAI_BASE_URL" if p["name"] == "openai" else "LLM_BASE_URL"):
        b = os.environ.get("OPENAI_BASE_URL" if p["name"] == "openai" else "LLM_BASE_URL")           # legacy override
    b = os.environ.get(p["name"].upper() + "_BASE_URL", b)
    return b.rstrip("/") if b else None


def _models(p: dict, prefer_model: str | None = None) -> list[tuple]:
    env = os.environ.get(p.get("model_env") or p["name"].upper() + "_MODEL", "")
    ms = [(m.strip(), True, S) for m in env.split(",") if m.strip()] or list(p["models"])
    if _pinned() == p["name"] and os.environ.get("LLM_MODEL"): ms.insert(0, (os.environ["LLM_MODEL"], True, S))
    if prefer_model and prefer_model not in [m[0] for m in ms]: ms.insert(0, (prefer_model, True, S))
    elif prefer_model: ms.sort(key=lambda m: m[0] != prefer_model)
    return ms


def usable() -> list[dict]:
    return [p for p in PROVIDERS if _paid_ok(p) and _base(p) and _keys(p)]


def configured() -> bool:
    return bool(usable())


def primary(need_tools: bool = False, prefer: str | None = None) -> dict | None:
    """First provider/model the router would try: {provider, base, model, key}. Used for status screens and legacy callers."""
    for c in _candidates(need_tools=need_tools, prefer=prefer, check_cooldown=False):
        return {"provider": c["name"], "base": c["base"], "model": c["model"], "key": c["key"]}
    return None


def _candidates(need_tools=False, prefer=None, model=None, purpose="chat", check_cooldown=True):
    names = usable()
    pin = (prefer or _pinned())
    names.sort(key=lambda p: p["name"] != pin)                           # stable: pinned/preferred first, rest keep priority order
    want_tier = F if purpose == "extract" else S                         # extraction: small+fast models; assistant/agent: best models
    for p in names:
        forced = model if p["name"] == prefer else None
        ms = sorted(_models(p, forced), key=lambda m: (m[0] != forced, m[2] != want_tier))
        if need_tools: ms = [m for m in ms if m[1]]
        for k in pool.rotate("llm:" + p["name"], _keys(p)):
            kid = f"llm:{p['name']}:{pool.fp(k)}"
            for mid, tools_ok, tier in ms:
                if check_cooldown and not (pool.available(kid) and pool.available(f"{kid}:{mid}") and pool.available(f"llm:{p['name']}:*:{mid}")): continue
                yield {"name": p["name"], "base": _base(p), "key": k, "model": mid, "kid": kid, "p": p}


# ------------------------------------------------------------------ transport
def _send(url: str, headers: dict, body: dict, timeout: float):
    import httpx
    r = httpx.post(url, headers=headers, json=body, timeout=timeout)
    ra = None
    try: ra = float(r.headers.get("retry-after"))
    except Exception: pass
    try: data = r.json()
    except Exception: data = None
    return r.status_code, data, (r.text or "")[:600], ra


def _headers(c: dict) -> dict:
    h = {"Authorization": "Bearer " + c["key"], "Content-Type": "application/json"}
    if c["name"] == "openrouter": h.update({"HTTP-Referer": os.environ.get("APP_URL", "https://localhost"), "X-Title": "Smart Sniper AI"})
    if c["name"] == "github": h.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    return h


_MODEL_ERR = re.compile(r"model|not\s*found|does\s*not\s*exist|decommission|deprecat|unsupported|not\s*supported|no\s*longer", re.I)


def _attempt(c: dict, body: dict, post, timeout: float):
    """-> ("ok", resp) | ("fail", scope, message, http_status). scope: key | model | transient. Cooldowns are applied here (real HTTP only)."""
    real = post is None
    body = {**body, "model": c["model"]}
    t0 = time.monotonic()
    try:
        if real:
            status, data, text, ra = _send(c["base"] + "/chat/completions", _headers(c), body, timeout)
            if status < 400 and isinstance(data, dict) and not data.get("choices") and data.get("error"):    # some gateways answer 200 with an error body
                e = data["error"]; status = int(e.get("code")) if str(e.get("code", "")).isdigit() else 502; text = str(e.get("message") or e)[:300]
        else:
            data = post(c["base"] + "/chat/completions", _headers(c), body); status, text, ra = 200, "", None
    except Exception as e:
        msg = pool.redact(f"{type(e).__name__}: {e}", c["key"])
        if real: pool.cool(c["kid"], 30, msg)
        pool.record(c["name"], False, msg)
        return "fail", "transient", msg, None
    if status >= 400:
        msg = pool.redact(f"HTTP {status}: {text}", c["key"])
        pool.record(c["name"], False, msg)
        if status in (400, 404, 422) and _MODEL_ERR.search(text or ""):
            pool.cool(f"{c['kid']}:{c['model']}", 3600, msg); pool.cool(f"llm:{c['name']}:*:{c['model']}", 3600, msg); return "fail", "model", msg, status
        if status in (400, 422):
            pool.cool(f"{c['kid']}:{c['model']}", 600, msg); return "fail", "model", msg, status
        if status == 429:
            pool.cool(f"{c['kid']}:{c['model']}", pool.cooldown_for(429, text, ra), msg)     # limits are per model on most providers
            return "fail", "model", msg, status
        pool.cool(c["kid"], pool.cooldown_for(status, text, ra), msg); return "fail", "key", msg, status
    try: ok = bool(data["choices"][0]["message"])
    except Exception: ok = False
    if not ok:
        msg = "empty response"; pool.record(c["name"], False, msg)
        if real: pool.cool(f"{c['kid']}:{c['model']}", 120, msg)
        return "fail", "model", msg, None
    pool.record(c["name"], True, ms=(time.monotonic() - t0) * 1000, model=c["model"])
    return "ok", data


def _day() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _spend(purpose: str):
    cap = _DAILY_CAPS.get(purpose)
    if not cap: return
    with _lock:
        u = _used.get(purpose)
        if not u or u[0] != _day(): u = _used[purpose] = [_day(), 0]
        if u[1] >= cap: raise BrainsUnavailable(f"daily free budget for '{purpose}' used up ({cap}); keeps the quota for the assistant")
        u[1] += 1


def complete(messages: list[dict], *, tools: list | None = None, temperature: float = 0.2, json_mode: bool = False, max_tokens: int | None = None,
             prefer: str | None = None, model: str | None = None, purpose: str = "chat", post=None, timeout: float = 30, budget: float = 55, cache: bool = False) -> dict:
    """Chat completion with automatic failover. Returns the provider response dict plus resp["_brain"]={provider, model, attempts}.
    post(url, headers, body)->dict can be injected (tests). Raises BrainsUnavailable when nothing could answer."""
    ck = None
    if cache and not tools:
        ck = hashlib.sha256(json.dumps([messages, json_mode, temperature], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with _lock:
            hit = _cache.get(ck)
            if hit and hit[0] > time.monotonic(): return json.loads(hit[1])
    if post is None: _spend(purpose)
    body: dict = {"messages": messages, "temperature": temperature}
    if tools: body.update(tools=tools, tool_choice="auto")
    if max_tokens: body["max_tokens"] = max_tokens
    deadline = time.monotonic() + budget
    errors: list[str] = []; n = 0; limited: dict[str, int] = {}
    for c in _candidates(need_tools=bool(tools), prefer=prefer, model=model, purpose=purpose, check_cooldown=post is None):
        if n >= MAX_ATTEMPTS or time.monotonic() > deadline: break
        b = dict(body)
        if json_mode and c["p"].get("json"): b["response_format"] = {"type": "json_object"}
        n += 1
        res = _attempt(c, b, post, min(timeout, max(5.0, deadline - time.monotonic())))
        if res[0] == "ok":
            resp = res[1]; resp["_brain"] = {"provider": c["name"], "model": c["model"], "attempts": n}
            if ck:
                with _lock:
                    if len(_cache) > 300: _cache.clear()
                    _cache[ck] = (time.monotonic() + 3600, json.dumps({k: v for k, v in resp.items()}, ensure_ascii=False))
            return resp
        errors.append(f"{c['name']}/{c['model']} ({res[1]}): {res[2]}")
        if res[3] == 429:                                   # two different models of one key both rate limited: the key itself is out
            limited[c["kid"]] = limited.get(c["kid"], 0) + 1
            if limited[c["kid"]] >= 2 and post is None: pool.cool(c["kid"], pool.cooldown_for(429, res[2]), res[2])
    raise BrainsUnavailable("; ".join(errors[-3:]) if errors else "no available free AI provider (all keys cooling down)")


def text_of(resp: dict) -> str:
    return (resp["choices"][0]["message"].get("content") or "").strip()


def parse_json(text: str) -> dict:
    """Tolerant JSON object parser: strips code fences and chatter around the object."""
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try: return json.loads(t)
    except Exception: pass
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        try: return json.loads(t[a:b + 1])
        except Exception: pass
    raise ValueError("no JSON object in model output")


# ------------------------------------------------------------------ status + live test (admin)
def status() -> dict:
    out = []
    for p in PROVIDERS:
        ks = _keys(p); base = _base(p); on = bool(ks and base and _paid_ok(p))
        st = pool.stats(p["name"])
        out.append({"name": p["name"], "label": p["label"], "configured": on, "keys": len(ks) if on else 0, "keys_cooling": pool.cooling(f"llm:{p['name']}:") if on else 0,
                    "models": [m[0] for m in _models(p)], "env": list(p["env"]), "paid": bool(p.get("paid")), "signup": p["url"], "note": p["note"],
                    "ok": st["ok"], "fail": st["fail"], "last_ok": st["last_ok"], "last_model": st["last_model"], "last_error": st["last_error"], "avg_ms": st["avg_ms"]})
    pr = primary()
    return {"configured": configured(), "active": [o["name"] for o in out if o["configured"]], "primary": {"provider": pr["provider"], "model": pr["model"]} if pr else None,
            "extract_used_today": (_used.get("extract") or [None, 0])[1] if (_used.get("extract") or [""])[0] == _day() else 0, "extract_cap": _DAILY_CAPS["extract"], "providers": out}


def ping(post=None) -> list[dict]:
    """One tiny request per configured key (max 3 per provider) so the admin can see which keys really work."""
    res = []
    for p in usable():
        for k in _keys(p)[:3]:
            m = _models(p)[0][0]; c = {"name": p["name"], "base": _base(p), "key": k, "model": m, "kid": f"llm:{p['name']}:{pool.fp(k)}", "p": p}
            t0 = time.monotonic()
            r = _attempt(c, {"messages": [{"role": "user", "content": "Reply with the single word OK."}], "max_tokens": 8, "temperature": 0}, post, 20)
            res.append({"provider": p["name"], "key": pool.fp(k), "model": m, "ok": r[0] == "ok", "ms": round((time.monotonic() - t0) * 1000), "error": None if r[0] == "ok" else r[2]})
    return res


def reset_state():
    pool.clear(); _cache.clear(); _used.clear()
