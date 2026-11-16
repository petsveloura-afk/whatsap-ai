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
  BRAINS_DISCOVER=0            (v3.12) turn off automatic model discovery. By default every provider is asked which models your key can really use
                               (GET <base>/models); the answer is ranked (newest + strongest first) and refreshed every 6 hours, so a retired model
                               name (HTTP 404 "model not found") fixes itself without a code change. <NAME>_MODEL=... still wins when set.
  BRAINS_KEYLESS=1             also allow the key-less community endpoint (OVHcloud). Off by default: it sends text to a third party.
Only the text needed for the task is ever sent. Keys never appear in logs, status or error messages.
"""
import hashlib, json, logging, math, os, re, threading, time
from . import pool

log = logging.getLogger("sniper")
# tier: "smart" = best quality (agent, tool calling) / "fast" = cheap + quick (extraction, short polishing)
S, F = "smart", "fast"
_CF_BASE = lambda: ("https://api.cloudflare.com/client/v4/accounts/%s/ai/v1" % os.environ["CLOUDFLARE_ACCOUNT_ID"]) if os.environ.get("CLOUDFLARE_ACCOUNT_ID") else None

# Priority order = default try order. Model ids change over time: each provider lists several, and a "model not found" answer
# simply moves on to the next one (and the bad one is skipped for an hour). Override any list with <NAME>_MODEL.
PROVIDERS: list[dict] = [
    {"name": "gemini", "label": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
     "models": [("gemini-2.5-flash", True, S), ("gemini-2.5-flash-lite", True, F), ("gemini-2.0-flash", True, F),
                ("gemini-flash-latest", True, S), ("gemini-flash-lite-latest", True, F)], "json": True,
     "url": "https://aistudio.google.com/apikey", "note": "חינם, בלי כרטיס אשראי. הכי טוב לעברית ולהקשר ארוך."},
    {"name": "groq", "label": "Groq", "base": "https://api.groq.com/openai/v1", "env": ("GROQ_API_KEY",),
     "models": [("llama-3.3-70b-versatile", True, S), ("openai/gpt-oss-120b", True, S), ("llama-3.1-8b-instant", False, F), ("openai/gpt-oss-20b", True, F),
                ("qwen/qwen3-32b", True, S), ("meta-llama/llama-4-scout-17b-16e-instruct", True, F)], "json": True,
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
    explicit = [(m.strip(), True, S) for m in env.split(",") if m.strip()]
    ms = explicit or _auto_models(p)                                    # v3.12: discovered + learned + static (an explicit <NAME>_MODEL still wins)
    if _pinned() == p["name"] and os.environ.get("LLM_MODEL"): ms.insert(0, (os.environ["LLM_MODEL"], True, S))
    if prefer_model and not explicit and _known_missing(p, prefer_model): prefer_model = None      # v3.12: do not force a model the provider no longer lists
    if prefer_model and prefer_model not in [m[0] for m in ms]: ms.insert(0, (prefer_model, True, S))
    elif prefer_model: ms.sort(key=lambda m: m[0] != prefer_model)
    return ms


def usable() -> list[dict]:
    return [p for p in PROVIDERS if _paid_ok(p) and _base(p) and _keys(p)]


def configured() -> bool:
    return bool(usable())


def primary(need_tools: bool = False, prefer: str | None = None) -> dict | None:
    """First provider/model the router would try: {provider, base, model, key}. Used for status screens and legacy callers."""
    for c in _candidates(need_tools=need_tools, prefer=prefer, check_cooldown=False, discover=False):
        return {"provider": c["name"], "base": c["base"], "model": c["model"], "key": c["key"]}
    return None


def _candidates(need_tools=False, prefer=None, model=None, purpose="chat", check_cooldown=True, discover=True):
    names = usable()
    pin = (prefer or _pinned())
    names.sort(key=lambda p: p["name"] != pin)                           # stable: pinned/preferred first, rest keep priority order
    want_tier = F if purpose == "extract" else S                         # extraction: small+fast models; assistant/agent: best models
    for p in names:
        if discover and check_cooldown: ensure_discovery(p)                # v3.12: learn which models this key can use (cached, max one call per TTL)
        forced = model if p["name"] == prefer else None
        ms = sorted(_models(p, forced), key=lambda m: (m[0] != forced, m[2] != want_tier))
        if need_tools: ms = [m for m in ms if m[1]]
        for k in pool.rotate("llm:" + p["name"], _keys(p)):
            kid = f"llm:{p['name']}:{pool.fp(k)}"; done: set = set()
            for mid, tools_ok, tier in ms:
                if check_cooldown and not (pool.available(kid) and pool.available(f"{kid}:{mid}") and pool.available(f"llm:{p['name']}:*:{mid}")): continue
                yield {"name": p["name"], "base": _base(p), "key": k, "model": mid, "kid": kid, "p": p}
                done.add(mid)
                for lm in list(_LEARNED.get(p["name"], [])):                  # v3.12: an error just told us the replacement name: try it right away
                    if lm in done or lm in [m[0] for m in ms]: continue
                    done.add(lm)
                    if check_cooldown and not (pool.available(kid) and pool.available(f"{kid}:{lm}") and pool.available(f"llm:{p['name']}:*:{lm}")): continue
                    yield {"name": p["name"], "base": _base(p), "key": k, "model": lm, "kid": kid, "p": p}


# ------------------------------------------------------------------ model discovery (v3.12)
# Why: providers retire model names (HTTP 404 "model not found" / "no longer available to new users"). Instead of guessing names in code, ask
# every provider which models THIS key can use (OpenAI-compatible GET <base>/models), rank them and use the best ones. Falls back to the
# static lists above when the provider has no /models endpoint or is unreachable. Free-only: OpenRouter is filtered to ":free" models, the paid
# OpenAI provider and Cloudflare are never queried.
_DISC: dict[str, dict] = {}              # provider -> {"ts", "ok", "ids", "err", "count"}
_LEARNED: dict[str, list[str]] = {}      # provider -> replacement model names that error messages suggested
_DISC_OK_TTL, _DISC_FAIL_TTL = 6 * 3600, 600
_NO_DISCOVER = {"openai", "cloudflare"}
_NOT_CHAT = re.compile(r"embed|whisper|tts|speech|audio|guard|moderat|rerank|imagen|image|veo|transcri|aqa|robotics|computer-use|dall-e|sora|diffusion|flux|"
                       r"stable-|clip|bge-|ocr|playai|orpheus|lyria|compound|safety|classif|search-preview|deep-research|(^|[-_/.:])live([-_.:]|$)|realtime", re.I)
_FASTRE = re.compile(r"(?<![a-z])(?:lite|mini|nano|small|instant|haiku|tiny)(?![a-z])|(?<![\d.])(?:1|2|3|4|7|8|9|12|14)(?:\.\d)?b(?![a-z])", re.I)
_NOTOOLS = re.compile(r"gemma|phi-|tinyllama|distill|(?<![\d.])(?:1|2|3|4|7|8)(?:\.\d)?b(?![a-z])", re.I)
_HINT = re.compile(r"(?:use|try|switch\s+to|replaced?\s+(?:it\s+)?(?:with|by)|recommend(?:ed)?)\s+(?:the\s+)?(?:model\s+)?[`'\"]?(?:models/)?([A-Za-z0-9][A-Za-z0-9._\-/:]{3,80})", re.I)


def _disc_on(p: dict) -> bool:
    flag = os.environ.get("BRAINS_DISCOVER", "")
    if flag == "0" or p["name"] in _NO_DISCOVER or p.get("paid"): return False
    if flag != "1" and os.environ.get("PYTEST_CURRENT_TEST"): return False           # unit tests never touch the network unless they ask for it
    return True


def _clean_id(mid) -> str:
    m = str(mid or "").strip()
    return m[len("models/"):] if m.startswith("models/") else m


def _parse_models(data) -> list[str]:
    """Model ids out of the common /models answers: {"data": [...]}, {"models": [...]}, or a bare list. Ids may be dicts (id / name / model) or strings."""
    items = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), list) else (data.get("models") if isinstance(data, dict) else data)
    out: list[str] = []
    for it in items if isinstance(items, list) else []:
        mid = it if isinstance(it, str) else (it.get("id") or it.get("name") or it.get("model")) if isinstance(it, dict) else None
        mid = _clean_id(mid)
        if mid and mid not in out and len(mid) < 120: out.append(mid)
    return out


def _chat_ids(p: dict, ids: list[str]) -> list[str]:
    ok = [m for m in ids if not _NOT_CHAT.search(m)]
    if p["name"] == "openrouter": ok = [m for m in ok if m.endswith(":free")]       # free-only guarantee
    return ok


def _fetch_models(url: str, headers: dict, timeout: float):
    import httpx
    r = httpx.get(url, headers=headers, timeout=timeout)
    try: data = r.json()
    except Exception: data = None
    return r.status_code, data, (r.text or "")[:300]


def _score(pname: str, mid: str) -> float:
    """Higher = better default choice. Newer version, bigger size, stable aliases and known strong families rank first; previews and tiny models rank last."""
    s = mid.lower(); sc = 0.0
    m = re.search(r"(?:gemini|llama|qwen|mistral|gemma|kimi|deepseek|grok|glm|command|nemotron)[-_ ]?v?(\d+(?:\.\d+)?)", s)
    if m:
        try: sc += min(float(m.group(1)), 20.0) * 4
        except ValueError: pass
    sizes = [float(x) for x in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)b(?![a-z])", s)]
    if sizes: sc += min(math.log2(max(sizes) + 1), 10.0) * 3
    if "gemini" in s:
        sc += 20 if "flash" in s else (10 if "pro" in s else 0)                    # flash has the generous free quota; pro is often not free
        if "lite" in s: sc -= 6
    if "gpt-oss" in s: sc += 14
    if re.search(r"qwen|kimi|deepseek|llama|mistral-(?:large|medium)", s): sc += 3
    if "latest" in s: sc += 3                                                     # stable alias, never retired
    if re.search(r"preview|exp(?:erimental)?\b|beta|-\d{2}-\d{2}|-\d{3}$", s): sc -= 4
    if "gemma" in s: sc -= 8
    return sc


def _rank(p: dict, ids: list[str]) -> list[tuple]:
    """Discovered ids -> [(id, tools_ok, tier)], strong models first inside each tier. Known static entries keep their curated flags."""
    static = {m[0]: m for m in p["models"]}
    rows = []
    for mid in _chat_ids(p, ids):
        if mid in static: _, t, tier = static[mid]
        else: tier = F if _FASTRE.search(mid) else S; t = not _NOTOOLS.search(mid)
        rows.append((mid, t, tier, _score(p["name"], mid)))
    smart = sorted([r for r in rows if r[2] == S], key=lambda r: -r[3])[:5]
    fast = sorted([r for r in rows if r[2] == F], key=lambda r: -r[3])[:4]
    return [(m, t, tier) for m, t, tier, _ in smart + fast]


def discover(p: dict, force: bool = False, fetch=None) -> dict:
    """Ask the provider which models the key can use. Cached: 6h after a success, 10 min after a failure. Never raises, never exposes the key."""
    name = p["name"]
    with _lock:
        d = _DISC.get(name)
        if d and not force and time.monotonic() - d["ts"] < (_DISC_OK_TTL if d["ok"] else _DISC_FAIL_TTL): return d
    base = _base(p); res = {"ts": time.monotonic(), "ok": False, "ids": [], "count": 0, "err": "no key"}
    fetch = fetch or _fetch_models
    for k in _keys(p)[:2]:
        h = _headers({"name": name, "key": k})
        try:
            status, data, text = fetch(base + "/models", h, 6.0)
        except Exception as e:
            res["err"] = pool.redact(f"{type(e).__name__}: {e}", k); break
        if status < 400:
            ids = _chat_ids(p, _parse_models(data))
            res.update(ok=bool(ids), ids=ids, count=len(ids), err=None if ids else "empty model list")
            break
        res["err"] = pool.redact(f"HTTP {status}: {text}", k)
        if status not in (401, 403): break                                         # a wrong URL / outage: another key will not help
    with _lock: _DISC[name] = res
    if res["ok"]: log.info("brains: %s offers %d chat models (best: %s)", name, res["count"], (_rank(p, res["ids"]) or [("-",)])[0][0])
    else: log.info("brains: model discovery for %s unavailable (%s); using the built-in list", name, res["err"])
    return res


def ensure_discovery(p: dict):
    try:
        if _disc_on(p) and not os.environ.get(p.get("model_env") or p["name"].upper() + "_MODEL"): discover(p)
    except Exception as e: log.info("brains: discovery skipped: %s", type(e).__name__)


def _discovered(p: dict):
    d = _DISC.get(p["name"])
    return _rank(p, d["ids"]) if d and d["ok"] else None


def _known_missing(p: dict, mid: str) -> bool:
    d = _DISC.get(p["name"])
    return bool(d and d["ok"] and mid not in d["ids"])


def _auto_models(p: dict) -> list[tuple]:
    """Order: names an error message told us to use, then (discovered union still-listed static names) strongest first. Without discovery: the static list."""
    static = list(p["models"]); learned = [(m, True, S) for m in _LEARNED.get(p["name"], [])]
    d = _discovered(p)
    if d is None: return learned + [m for m in static if m[0] not in _LEARNED.get(p["name"], [])]
    ids = _DISC[p["name"]]["ids"]
    pool_ = {m[0]: m for m in static if m[0] in ids}
    for m in d: pool_.setdefault(m[0], m)
    ordered = sorted(pool_.values(), key=lambda m: -_score(p["name"], m[0]))
    smart = [m for m in ordered if m[2] == S]; fast = [m for m in ordered if m[2] != S]
    out = learned + [m for m in smart + fast if m[0] not in _LEARNED.get(p["name"], [])]
    return out[:10] or list(static)


def _learn(pname: str, text: str, failed: str):
    """Error messages sometimes name the replacement ("update your code to use models/gemini-3.8-flash"): remember it and try it next."""
    for m in _HINT.finditer(text or ""):
        cand = _clean_id(m.group(1).rstrip(".,:;)"))
        if cand == failed or not re.search(r"[A-Za-z]", cand) or not ("-" in cand or "/" in cand) or _NOT_CHAT.search(cand) or cand.lower().startswith("http"): continue
        with _lock:
            lst = _LEARNED.setdefault(pname, [])
            if cand not in lst: lst.insert(0, cand); del lst[5:]
        return


def best_model(pname: str, need_tools: bool = False) -> str | None:
    """Best discovered model of a provider (cache only, no network); None when nothing was discovered yet."""
    p = BY_NAME.get(pname)
    if not p: return None
    for mid, t, tier in _auto_models(p) if _DISC.get(pname, {}).get("ok") or _LEARNED.get(pname) else []:
        if tier == S and (t or not need_tools): return mid
    return None


def refresh_models(fetch=None) -> list[dict]:
    """Force a fresh discovery for every usable provider (admin button). Returns a short per-provider summary; no keys."""
    out = []
    for p in usable():
        if not _disc_on(p) and os.environ.get("BRAINS_DISCOVER") != "1":
            out.append({"provider": p["name"], "ok": False, "count": 0, "error": "discovery off for this provider", "models": [m[0] for m in _models(p)][:6]}); continue
        d = discover(p, force=True, fetch=fetch)
        out.append({"provider": p["name"], "ok": d["ok"], "count": d["count"], "error": d["err"], "models": [m[0] for m in _models(p)][:6]})
    return out


def warm():
    """Background warm-up at start-up so the first user request does not pay for discovery."""
    def run():
        time.sleep(3)
        for p in usable(): ensure_discovery(p)
    threading.Thread(target=run, daemon=True, name="brains-warm").start()


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
            if real: _learn(c["name"], text, c["model"])                   # v3.12: "please use models/xyz" -> try xyz next
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
def _disc_view(p: dict) -> dict:
    d = _DISC.get(p["name"])
    if not d: return {"on": _disc_on(p), "ok": None, "count": 0, "age_s": None, "error": None}
    return {"on": _disc_on(p), "ok": d["ok"], "count": d["count"], "age_s": int(time.monotonic() - d["ts"]), "error": d["err"]}


def status() -> dict:
    out = []
    for p in PROVIDERS:
        ks = _keys(p); base = _base(p); on = bool(ks and base and _paid_ok(p))
        st = pool.stats(p["name"])
        out.append({"name": p["name"], "label": p["label"], "configured": on, "keys": len(ks) if on else 0, "keys_cooling": pool.cooling(f"llm:{p['name']}:") if on else 0,
                    "models": [m[0] for m in _models(p)], "env": list(p["env"]), "paid": bool(p.get("paid")), "signup": p["url"], "note": p["note"],
                    "ok": st["ok"], "fail": st["fail"], "last_ok": st["last_ok"], "last_model": st["last_model"], "last_error": st["last_error"], "avg_ms": st["avg_ms"],
                    "discovery": _disc_view(p) if on else None, "learned": list(_LEARNED.get(p["name"], []))})
    pr = primary()
    return {"configured": configured(), "active": [o["name"] for o in out if o["configured"]], "primary": {"provider": pr["provider"], "model": pr["model"]} if pr else None,
            "extract_used_today": (_used.get("extract") or [None, 0])[1] if (_used.get("extract") or [""])[0] == _day() else 0, "extract_cap": _DAILY_CAPS["extract"], "providers": out}


def ping(post=None) -> list[dict]:
    """One tiny request per configured key (max 3 per provider) so the admin can see which keys really work."""
    res = []
    for p in usable():
        if post is None: ensure_discovery(p)                                  # v3.12: find out which models this key can really use first
        for k in _keys(p)[:3]:
            t0 = time.monotonic(); tried: list[str] = []; r = ("fail", "transient", "no model", None); m = ""
            for m in [x[0] for x in _models(p)][:4]:                         # v3.12: a retired model name moves on to the next one instead of failing the test
                c = {"name": p["name"], "base": _base(p), "key": k, "model": m, "kid": f"llm:{p['name']}:{pool.fp(k)}", "p": p}
                tried.append(m)
                r = _attempt(c, {"messages": [{"role": "user", "content": "Reply with the single word OK."}], "max_tokens": 8, "temperature": 0}, post, 20)
                if r[0] == "ok" or r[1] != "model" or r[3] == 429: break
            res.append({"provider": p["name"], "key": pool.fp(k), "model": m, "ok": r[0] == "ok", "ms": round((time.monotonic() - t0) * 1000),
                        "error": None if r[0] == "ok" else r[2], "tried": tried})
    return res


def reset_state():
    pool.clear(); _cache.clear(); _used.clear(); _DISC.clear(); _LEARNED.clear()
