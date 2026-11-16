"""v3.12 model discovery: retired model names fix themselves. No network: /models and chat calls are replaced by fakes."""
import json
import pytest
from app import brains, pool

KEYS = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY", "GITHUB_MODELS_TOKEN", "SAMBANOVA_API_KEY",
        "NVIDIA_API_KEY", "HF_TOKEN", "HUGGINGFACE_API_KEY", "CLOUDFLARE_API_TOKEN", "CUSTOM_LLM_KEY", "OLLAMA_API_KEY", "OLLAMA_BASE_URL", "OVH_API_KEY", "OPENAI_API_KEY",
        "LLM_PROVIDER", "LLM_MODEL", "BRAINS_KEYLESS", "BRAINS_ALLOW_PAID", "GEMINI_MODEL", "GROQ_MODEL", "BRAINS_DISCOVER"]
M = [{"role": "user", "content": "x"}]


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in KEYS: monkeypatch.delenv(k, raising=False)
    brains.reset_state(); yield; brains.reset_state()


def reply(t="ok"): return {"choices": [{"message": {"content": t}}]}


def _p(name): return brains.BY_NAME[name]


GEMINI_LIST = {"data": [{"id": "models/gemini-3.8-flash"}, {"id": "models/gemini-3.8-flash-lite"}, {"id": "models/gemini-3.8-pro"}, {"id": "models/gemini-embedding-001"},
                        {"id": "models/gemini-3.8-flash-image"}, {"id": "models/gemini-3.8-flash-tts"}, {"id": "models/gemma-3-27b-it"}, {"id": "models/gemini-flash-latest"}]}
GROQ_LIST = {"data": [{"id": "openai/gpt-oss-120b"}, {"id": "openai/gpt-oss-20b"}, {"id": "whisper-large-v3"}, {"id": "llama-3.1-8b-instant"}, {"id": "meta-llama/llama-guard-4-12b"},
                      {"id": "qwen/qwen3-32b"}, {"id": "playai-tts"}, {"id": "groq/compound"}]}


def test_parse_and_filter_models():
    assert brains._parse_models(GEMINI_LIST)[0] == "gemini-3.8-flash"                      # "models/" prefix stripped
    assert brains._parse_models({"models": [{"name": "models/a-b"}, "c-d"]}) == ["a-b", "c-d"] and brains._parse_models(None) == [] and brains._parse_models("x") == []
    ids = brains._chat_ids(_p("gemini"), brains._parse_models(GEMINI_LIST))
    assert "gemini-embedding-001" not in ids and "gemini-3.8-flash-image" not in ids and "gemini-3.8-flash-tts" not in ids and "gemini-3.8-flash" in ids
    g = brains._chat_ids(_p("groq"), brains._parse_models(GROQ_LIST))
    assert g == ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.1-8b-instant", "qwen/qwen3-32b"]
    orr = brains._chat_ids(_p("openrouter"), ["a/b:free", "paid/model", "x/y"]); assert orr == ["a/b:free"]       # free-only


def test_ranking_prefers_new_flash_and_keeps_tiers():
    r = brains._rank(_p("gemini"), brains._chat_ids(_p("gemini"), brains._parse_models(GEMINI_LIST)))
    smart = [m[0] for m in r if m[2] == brains.S]; fast = [m[0] for m in r if m[2] == brains.F]
    assert smart[0] in ("gemini-3.8-flash", "gemini-flash-latest") and "gemini-3.8-flash-lite" in fast and smart.index("gemini-3.8-flash") < smart.index("gemini-3.8-pro")
    rg = brains._rank(_p("groq"), brains._chat_ids(_p("groq"), brains._parse_models(GROQ_LIST)))
    assert rg[0][0] == "openai/gpt-oss-120b" and ("llama-3.1-8b-instant", False, brains.F) in rg


def test_discovery_replaces_retired_models(monkeypatch):
    monkeypatch.setenv("BRAINS_DISCOVER", "1"); monkeypatch.setenv("GEMINI_API_KEY", "g1"); seen = []
    monkeypatch.setattr(brains, "_fetch_models", lambda url, h, t: (200, GEMINI_LIST, ""))
    def send(url, headers, body, timeout):
        seen.append(body["model"])
        return (404, None, "model not found", None) if body["model"] == "gemini-2.5-flash" else (200, reply("fine"), "", None)
    monkeypatch.setattr(brains, "_send", send)
    r = brains.complete(M, purpose="agent")
    assert r["_brain"]["model"] in ("gemini-3.8-flash", "gemini-flash-latest") and "gemini-2.5-flash" not in seen        # the dead name is never even tried
    assert brains.best_model("gemini") == r["_brain"]["model"]
    st = {p["name"]: p for p in brains.status()["providers"]}["gemini"]
    assert st["discovery"]["ok"] and st["discovery"]["count"] >= 4 and "g1" not in json.dumps(brains.status())


def test_discovery_failure_falls_back_to_static_list(monkeypatch):
    monkeypatch.setenv("BRAINS_DISCOVER", "1"); monkeypatch.setenv("GROQ_API_KEY", "SECRETQ")
    monkeypatch.setattr(brains, "_fetch_models", lambda url, h, t: (_ for _ in ()).throw(RuntimeError("boom SECRETQ")))
    seen = []; monkeypatch.setattr(brains, "_send", lambda u, h, b, t: seen.append(b["model"]) or (200, reply(), "", None))
    brains.complete(M, purpose="agent"); assert seen == ["llama-3.3-70b-versatile"]
    d = brains.status()["providers"][1]["discovery"]; assert d["ok"] is False and "SECRETQ" not in json.dumps(brains.status())


def test_explicit_model_env_beats_discovery(monkeypatch):
    monkeypatch.setenv("BRAINS_DISCOVER", "1"); monkeypatch.setenv("GROQ_API_KEY", "q1"); monkeypatch.setenv("GROQ_MODEL", "my-model")
    calls = []; monkeypatch.setattr(brains, "_fetch_models", lambda *a: calls.append(a) or (200, GROQ_LIST, ""))
    seen = []; monkeypatch.setattr(brains, "_send", lambda u, h, b, t: seen.append(b["model"]) or (200, reply(), "", None))
    brains.complete(M); assert seen == ["my-model"] and calls == []


def test_error_message_suggestion_is_learned(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g1"); seen = []
    msg = "This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.8-flash for the latest features."
    def send(url, headers, body, timeout):
        seen.append(body["model"])
        return (404, None, msg, None) if body["model"] != "gemini-3.8-flash" else (200, reply("yes"), "", None)
    monkeypatch.setattr(brains, "_send", send)
    r = brains.complete(M, purpose="agent")
    assert r["_brain"]["model"] == "gemini-3.8-flash" and seen[0] == "gemini-2.5-flash" and seen[1] == "gemini-3.8-flash"
    seen.clear(); brains.complete(M, purpose="agent"); assert seen == ["gemini-3.8-flash"]                       # remembered: first try next time
    brains._learn("groq", "Please use the Interactions API", "x"); assert "groq" not in brains._LEARNED        # prose is not a model name


def test_ping_moves_past_a_retired_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "q1"); seen = []
    def send(url, headers, body, timeout):
        seen.append(body["model"])
        return (404, None, "The model `llama-3.3-70b-versatile` does not exist", None) if body["model"] == "llama-3.3-70b-versatile" else (200, reply("OK"), "", None)
    monkeypatch.setattr(brains, "_send", send)
    r = brains.ping()[0]
    assert r["ok"] and r["model"] == "openai/gpt-oss-120b" and r["tried"] == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]


def test_refresh_models_summary(monkeypatch):
    monkeypatch.setenv("BRAINS_DISCOVER", "1"); monkeypatch.setenv("GROQ_API_KEY", "q1")
    monkeypatch.setattr(brains, "_fetch_models", lambda url, h, t: (200, GROQ_LIST, ""))
    out = brains.refresh_models()
    assert out[0]["provider"] == "groq" and out[0]["ok"] and out[0]["count"] == 4 and out[0]["models"][0] == "openai/gpt-oss-120b"
    monkeypatch.setattr(brains, "_fetch_models", lambda url, h, t: (401, None, "invalid key"))
    assert brains.refresh_models()[0]["ok"] is False


def test_paid_and_cloudflare_are_never_queried(monkeypatch):
    monkeypatch.setenv("BRAINS_DISCOVER", "1")
    assert not brains._disc_on(_p("openai")) and not brains._disc_on(_p("cloudflare")) and brains._disc_on(_p("groq"))
    monkeypatch.setenv("BRAINS_DISCOVER", "0"); assert not brains._disc_on(_p("groq"))


def test_admin_refresh_endpoint(monkeypatch):
    import os
    from tests.test_core import c, tok
    monkeypatch.setenv("BRAINS_DISCOVER", "1"); monkeypatch.setenv("GROQ_API_KEY", "q1")
    monkeypatch.setattr(brains, "_fetch_models", lambda url, h, t: (200, GROQ_LIST, ""))
    os.environ["SUPER_ADMIN_EMAILS"] = "root@x.com"
    h = tok("root@x.com"); user = tok("plain-disc@x.com")
    assert c.post("/api/admin/brains/models/refresh", headers=user).status_code == 403
    d = c.post("/api/admin/brains/models/refresh", headers=h).json()
    assert d["results"][0]["provider"] == "groq" and d["results"][0]["ok"] and "q1" not in json.dumps(d)
    g = [p for p in d["status"]["providers"] if p["name"] == "groq"][0]
    assert g["discovery"]["ok"] and g["models"][0] == "openai/gpt-oss-120b"
