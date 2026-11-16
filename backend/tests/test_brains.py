"""Brains router + key pool + multi-engine search. No network, no real keys: HTTP is replaced by fakes."""
import os, json
import pytest
from tests.test_core import c, tok
from app import brains, pool, llm, discovery, agent

ALL_KEYS = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY", "GITHUB_MODELS_TOKEN", "SAMBANOVA_API_KEY",
            "NVIDIA_API_KEY", "HF_TOKEN", "HUGGINGFACE_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "CUSTOM_LLM_KEY", "CUSTOM_LLM_BASE_URL", "OLLAMA_API_KEY",
            "OLLAMA_BASE_URL", "OVH_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "BRAINS_KEYLESS", "BRAINS_ALLOW_PAID", "AGENT_PROVIDER",
            "AGENT_MODEL", "GEMINI_MODEL", "GROQ_MODEL", "BRAINS_AUTO_ENABLE"] + [f"{k}_{i}" for k in ("GROQ_API_KEY", "GEMINI_API_KEY") for i in range(2, 5)]
SEARCH_KEYS = ["BRAVE_API_KEY", "TAVILY_API_KEY", "SERPER_API_KEY", "EXA_API_KEY", "JINA_API_KEY", "GOOGLE_CSE_KEY", "GOOGLE_CSE_CX", "SEARXNG_URL", "TAVILY_API_KEY_2"]


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ALL_KEYS + SEARCH_KEYS: monkeypatch.delenv(k, raising=False)
    brains.reset_state(); yield; brains.reset_state()


def reply(text="hi"): return {"choices": [{"message": {"content": text}}]}
M = [{"role": "user", "content": "x"}]


def test_keys_parse_multiple_formats(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "a1, b2\nc3;a1"); monkeypatch.setenv("GROQ_API_KEY_2", "d4")
    assert pool.keys("GROQ_API_KEY") == ["a1", "b2", "c3", "d4"]
    assert pool.keys("MISSING") == []


def test_no_keys_means_not_configured_and_paid_never_auto(monkeypatch):
    assert not brains.configured() and brains.primary() is None
    monkeypatch.setenv("OPENAI_API_KEY", "sk-paid")
    assert not brains.configured()                                   # paid provider needs explicit opt-in
    monkeypatch.setenv("LLM_PROVIDER", "openai"); assert brains.configured()
    monkeypatch.delenv("LLM_PROVIDER"); monkeypatch.setenv("BRAINS_ALLOW_PAID", "1"); assert brains.configured()
    monkeypatch.delenv("OPENAI_API_KEY"); monkeypatch.delenv("BRAINS_ALLOW_PAID")
    with pytest.raises(brains.BrainsUnavailable): brains.complete(M)


def test_keyless_provider_is_opt_in(monkeypatch):
    assert "ovh" not in [p["name"] for p in brains.usable()]
    monkeypatch.setenv("BRAINS_KEYLESS", "1"); assert "ovh" in [p["name"] for p in brains.usable()]


def test_failover_across_providers_and_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g1"); monkeypatch.setenv("GROQ_API_KEY", "q1,q2")
    calls = []
    def send(url, headers, body, timeout):
        calls.append((url.split("/")[2], headers["Authorization"][-2:], body["model"]))
        if "generativelanguage" in url: return 429, {"error": {"message": "rate"}}, "rate limit", 20
        if headers["Authorization"].endswith("q1"): return 401, None, "invalid api key", None
        return 200, reply("from-groq-q2"), "", None
    monkeypatch.setattr(brains, "_send", send)
    r = brains.complete(M)
    assert r["choices"][0]["message"]["content"] == "from-groq-q2" and r["_brain"]["provider"] == "groq"
    n = len(calls); brains.complete(M)
    assert len(calls) == n + 1                                  # gemini + groq q1 are resting now: straight to the working key
    st = {p["name"]: p for p in brains.status()["providers"]}
    assert st["groq"]["keys"] == 2 and st["groq"]["keys_cooling"] >= 1 and st["gemini"]["configured"] and "g1" not in json.dumps(brains.status())


def test_bad_model_name_moves_to_next_model_and_is_remembered(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "q1"); seen = []
    def send(url, headers, body, timeout):
        seen.append(body["model"])
        return (404, None, "The model `llama-3.3-70b-versatile` does not exist", None) if body["model"] == "llama-3.3-70b-versatile" else (200, reply("ok"), "", None)
    monkeypatch.setattr(brains, "_send", send)
    assert brains.text_of(brains.complete(M, purpose="agent")) == "ok"
    seen.clear(); brains.complete(M, purpose="agent")
    assert "llama-3.3-70b-versatile" not in seen               # not retried for an hour


def test_all_down_raises_unavailable_without_leaking_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "SECRETKEY123")
    monkeypatch.setattr(brains, "_send", lambda *a, **k: (500, None, "boom SECRETKEY123", None))
    with pytest.raises(brains.BrainsUnavailable) as e: brains.complete(M)
    assert "SECRETKEY123" not in str(e.value) and "SECRETKEY123" not in json.dumps(brains.status())
    with pytest.raises(brains.BrainsUnavailable): brains.complete(M)       # now resting: fails fast, no hammering
    assert llm.chat("s", "u") is None                                      # helpers never raise


def test_tools_only_go_to_tool_capable_models(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "q1"); monkeypatch.setenv("GROQ_MODEL", "x")
    seen = []
    monkeypatch.setattr(brains, "_send", lambda u, h, b, t: seen.append(b["model"]) or (200, reply(), "", None))
    brains.complete(M, tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}], purpose="agent")
    brains.reset_state(); monkeypatch.delenv("GROQ_MODEL")
    brains.complete(M, tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}], purpose="agent")
    assert seen[1] not in ("llama-3.1-8b-instant",) and seen[1] == "llama-3.3-70b-versatile"


def test_extraction_prefers_fast_models_and_is_cached_and_capped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "q1"); seen = []
    monkeypatch.setattr(brains, "_send", lambda u, h, b, t: seen.append(b["model"]) or (200, reply('```json\n{"rooms": 3, "location": "Holon"}\n```'), "", None))
    out = llm.enhance("דירה", {"category": None, "price": 5000})
    assert seen == ["llama-3.1-8b-instant"] and out["rooms"] == 3.0 and out["location"] == "Holon" and out["extraction"] == "rules+llm"
    llm.enhance("דירה", {"category": None, "price": 5000}); assert len(seen) == 1             # same text: served from cache
    monkeypatch.setitem(brains._DAILY_CAPS, "extract", 1)
    assert llm.enhance("אחר", {"category": None}) == {"category": None}                         # cap reached: silently rules only
    assert llm.enhance("x", {k: 1 for k in llm._KEYS}) == {k: 1 for k in llm._KEYS} and len(seen) == 1   # nothing missing: no call at all


def test_parse_json_is_tolerant():
    assert brains.parse_json('blah {"a": 1} bye') == {"a": 1}
    assert brains.parse_json('```json\n{"a": 2}\n```') == {"a": 2}
    with pytest.raises(ValueError): brains.parse_json("no json here")


def test_injected_post_and_legacy_cfg(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    assert llm._cfg()[0].startswith("https://api.groq.com") and llm.chat("s", "u", post=lambda u, h, j: reply(" hi ")) == "hi"
    assert llm.chat("s", "u", post=lambda u, h, j: 1 / 0) is None


def test_custom_and_cloudflare_need_their_url(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t"); assert "cloudflare" not in [p["name"] for p in brains.usable()]
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc1")
    cf = [p for p in brains.usable() if p["name"] == "cloudflare"][0]; assert brains._base(cf).endswith("/accounts/acc1/ai/v1")
    monkeypatch.setenv("CUSTOM_LLM_KEY", "k"); assert "custom" not in [p["name"] for p in brains.usable()]
    monkeypatch.setenv("CUSTOM_LLM_BASE_URL", "http://lm.local/v1/"); monkeypatch.setenv("CUSTOM_LLM_MODEL", "mine")
    cu = [p for p in brains.usable() if p["name"] == "custom"][0]; assert brains._base(cu) == "http://lm.local/v1" and brains._models(cu)[0][0] == "mine"


def test_agent_fails_over_between_providers_and_reports_who_answered(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g1"); monkeypatch.setenv("GROQ_API_KEY", "q1")
    def send(url, headers, body, timeout):
        if "generativelanguage" in url: return 503, None, "overloaded", None
        return 200, {"choices": [{"message": {"content": "שלום", "tool_calls": None}}]}, "", None
    monkeypatch.setattr(brains, "_send", send)
    from app.db import SessionLocal
    from app.models import User
    from sqlalchemy import select
    tok("br1@x.com")
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "br1@x.com")); res = agent.run(db, u, "היי")
    assert res["reply"] == "שלום" and res["provider"] == "groq"


def test_tool_calls_without_ids_get_ids(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g1"); from app.db import SessionLocal; from app.models import User; from sqlalchemy import select
    tok("br2@x.com"); seen = []
    steps = iter([{"content": None, "tool_calls": [{"function": {"name": "list_searches", "arguments": "{}"}}]}, {"content": "סיימתי"}])
    def post(url, headers, body): seen.append(body); return {"choices": [{"message": next(steps)}]}
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "br2@x.com")); assert agent.run(db, u, "מה יש", post)["reply"] == "סיימתי"
    asst = [m for m in seen[1]["messages"] if m["role"] == "assistant"][0]
    assert asst["tool_calls"][0]["id"] and asst["tool_calls"][0]["type"] == "function"
    assert [m for m in seen[1]["messages"] if m["role"] == "tool"][0]["tool_call_id"] == asst["tool_calls"][0]["id"]


def test_gemini_multi_key_value_is_split_for_agent_cfg(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "aaa,bbb"); assert agent.cfg()["key"] == "aaa"
    monkeypatch.setenv("AGENT_PROVIDER", "groq"); monkeypatch.setenv("GROQ_API_KEY", "q"); assert agent.cfg()["provider"] == "groq"


# ---------------- web search engines ----------------
def test_search_rotates_keys_and_falls_over_between_engines(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "t1,t2"); monkeypatch.setenv("SERPER_API_KEY", "s1")
    assert discovery.providers() == ["tavily", "serper"] and discovery.provider() == "tavily"
    calls = []
    def http(method, url, headers, params=None, json=None):
        calls.append((url.split("/")[2], headers.get("Authorization") or headers.get("X-API-KEY")))
        if "tavily" in url: raise discovery.SearchHTTPError(429, "monthly quota exceeded")
        return {"organic": [{"title": "דירה בחולון", "link": "https://x.co.il/1", "snippet": "3 חדרים 5,000 ש״ח"}]}
    monkeypatch.setattr(discovery, "_http", http)
    r = discovery.search("דירה חולון", 5)
    assert r[0]["url"] == "https://x.co.il/1" and [x[0] for x in calls] == ["api.tavily.com", "api.tavily.com", "google.serper.dev"]   # both tavily keys tried
    calls.clear(); discovery.search("דירה חולון", 5)
    assert [x[0] for x in calls] == ["google.serper.dev"]                      # tavily keys are resting (monthly quota): no hammering


def test_search_tops_up_from_second_engine_and_dedupes(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "t1"); monkeypatch.setenv("SERPER_API_KEY", "s1")
    def http(method, url, headers, params=None, json=None):
        if "tavily" in url: return {"results": [{"title": "a", "url": "https://a.co/1", "content": "x"}]}
        return {"organic": [{"title": "a", "link": "https://a.co/1", "snippet": "dup"}, {"title": "b", "link": "https://b.co/2", "snippet": "y"}]}
    monkeypatch.setattr(discovery, "_http", http)
    assert [x["url"] for x in discovery.search("דירה חולון", 10)] == ["https://a.co/1", "https://b.co/2"]


def test_search_errors_and_keyless_searxng(monkeypatch):
    with pytest.raises(RuntimeError, match="no web search key"): discovery.search("דירה")
    monkeypatch.setenv("SEARXNG_URL", "http://127.0.0.1:8080/")
    seen = {}
    monkeypatch.setattr(discovery, "_http", lambda m, u, h, params=None, json=None: seen.update(u=u, p=params) or {"results": [{"title": "t", "url": "https://z.co/1", "content": "c"}]})
    assert discovery.search("דירה חולון")[0]["snippet"] == "c" and seen["u"] == "http://127.0.0.1:8080/search" and seen["p"]["format"] == "json"
    monkeypatch.setenv("TAVILY_API_KEY", "SECRETT"); monkeypatch.delenv("SEARXNG_URL")
    def boom(*a, **k): raise discovery.SearchHTTPError(500, "SECRETT")
    monkeypatch.setattr(discovery, "_http", boom)
    with pytest.raises(RuntimeError) as e: discovery.search("דירה חולון")
    assert "SECRETT" not in str(e.value)


def test_google_cse_needs_cx(monkeypatch):
    monkeypatch.setenv("GOOGLE_CSE_KEY", "k"); assert "google_cse" not in discovery.providers()
    monkeypatch.setenv("GOOGLE_CSE_CX", "cx"); assert "google_cse" in discovery.providers()


# ---------------- admin API ----------------
def _admin():
    os.environ["SUPER_ADMIN_EMAILS"] = "root@x.com"
    return tok("root@x.com")


def test_admin_brains_endpoints(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "q1,q2"); monkeypatch.setenv("TAVILY_API_KEY", "t1")
    h = _admin(); user = tok("plain-br@x.com")
    assert c.get("/api/admin/brains", headers=user).status_code == 403 and c.get("/api/admin/brains").status_code == 401
    d = c.get("/api/admin/brains", headers=h).json()
    g = [p for p in d["llm"]["providers"] if p["name"] == "groq"][0]
    assert g["configured"] and g["keys"] == 2 and "q1" not in json.dumps(d) and [s for s in d["search"] if s["name"] == "tavily"][0]["keys"] == 1
    assert len(d["llm"]["providers"]) >= 12 and "gemini" in d["llm"]["providers"][0]["name"]
    monkeypatch.setattr(brains, "_send", lambda u, h_, b, t: (200, reply("OK"), "", None))
    r = c.post("/api/admin/brains/test", headers=h).json()["results"]
    assert len(r) == 2 and all(x["ok"] for x in r) and all(len(x["key"]) == 6 and x["key"] not in ("q1", "q2") for x in r)
    st = c.get("/api/agent/status", headers=h).json()
    assert st["brains"] == ["groq"] and st["web_searches"] == ["tavily"] and st["web_search"] == "tavily"
    assert "groq" in c.get("/api/admin/system-settings", headers=h).json()["capabilities"]["brains"]


def test_auto_enable_flag_default(monkeypatch):
    from app import flags
    assert flags._defaults()["llm_extraction"] is False
    monkeypatch.setenv("BRAINS_AUTO_ENABLE", "1"); assert flags._defaults()["llm_extraction"] is True
