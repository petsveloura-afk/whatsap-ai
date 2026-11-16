"""Agent tests: no network, no real key. The model is replaced by a scripted fake that speaks the OpenAI tool-calling format."""
import json
from tests.test_core import c, tok
from app import agent
from app.db import SessionLocal
from app.models import User
from sqlalchemy import select

TXT = "דירת 3 חדרים בחולון, משופצת, ללא תיווך, 5,200 ש״ח."


def _call(name, args, i="c1"):
    return {"id": i, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def script(*steps):
    """Fake provider: returns each scripted assistant message in order; records what it was sent."""
    seen = []
    it = iter(steps)
    def post(url, headers, body):
        seen.append(body)
        return {"choices": [{"message": next(it)}]}
    post.seen = seen
    return post


def _user(email):
    with SessionLocal() as db: return db.scalar(select(User).where(User.email == email))


def _setup(email):
    h = tok(email)
    sid = c.post("/api/searches", headers=h, json={"name": "s", "category": "real_estate", "location": "Holon", "max_price": 5500}).json()["id"]
    lid = c.post("/api/listings/ingest", headers=h, json={"search_id": sid, "text": TXT}).json()["id"]
    return h, sid, lid


def test_status_and_rules_fallback_without_key(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"): monkeypatch.delenv(k, raising=False)
    h, sid, lid = _setup("ag1@x.com")
    assert c.get("/api/agent/status", headers=h).json()["mode"] == "rules"
    r = c.post("/api/agent/chat", headers=h, json={"message": "מה הכי מתאים בחולון?"}).json()
    assert r["mode"] == "rules" and "Holon" in r["reply"]
    assert c.post("/api/agent/chat", headers=h, json={"message": "תזכור שהתקציב שלי 5500"}).json()["mode"] == "rules"
    assert any("5500" in m["text"] for m in c.get("/api/agent/memory", headers=h).json()["items"])
    assert len(c.get("/api/agent/history", headers=h).json()["items"]) == 4


def test_auth_required():
    assert c.post("/api/agent/chat", json={"message": "hi"}).status_code == 401
    assert c.get("/api/agent/memory").status_code == 401


def test_tool_loop_reads_and_acts(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("LLM_PROVIDER", raising=False)
    h, sid, lid = _setup("ag2@x.com"); u = _user("ag2@x.com")
    post = script({"content": None, "tool_calls": [_call("find_listings", {"location": "חולון"}, "a"), _call("mark_listing", {"listing_id": lid, "action": "save"}, "b")]},
                  {"content": "שמרתי את המודעה בחולון."})
    with SessionLocal() as db:
        res = agent.run(db, u, "תשמור לי את הכי טובה בחולון", post)
    assert res["mode"] == "agent" and res["reply"].startswith("שמרתי")
    assert res["actions"][0]["tool"] == "mark_listing"
    second = post.seen[1]["messages"]
    tool_msgs = [m for m in second if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and json.loads(tool_msgs[0]["content"])["total_matching"] == 1
    assert c.get("/api/listings", headers=h).json()[0]["status"] == "saved"
    assert len(c.get("/api/memory", headers=h).json()["items"]) == 1   # existing personalization learned from the agent's action


def test_tools_are_user_scoped(monkeypatch):
    h1, sid1, lid1 = _setup("ag3@x.com"); h2, sid2, lid2 = _setup("ag4@x.com"); u2 = _user("ag4@x.com")
    actions = []
    with SessionLocal() as db:
        tb = agent.Toolbox(db, u2, actions)
        assert tb.dispatch("get_listing", {"listing_id": lid1})["error"] == "listing not found"
        assert tb.dispatch("mark_listing", {"listing_id": lid1, "action": "reject"})["error"] == "listing not found"
        assert tb.dispatch("set_search_active", {"search_id": sid1, "active": False})["error"] == "search not found"
        assert tb.dispatch("find_listings", {"search_id": sid1})["error"] == "search not found"
        assert tb.dispatch("delete_everything", {})["error"] == "unknown tool"
        assert tb.dispatch("get_listing", {"listing_id": lid2})["id"] == lid2 and actions == []
    assert c.get("/api/listings", headers=h1).json()[0]["status"] == "new"


def test_create_search_respects_plan_limit_and_pause(monkeypatch):
    h = tok("ag5@x.com"); u = _user("ag5@x.com"); actions = []
    with SessionLocal() as db:
        tb = agent.Toolbox(db, u, actions)
        ids = [tb.dispatch("create_search", {"name": f"n{i}", "category": "vehicles"}) for i in range(4)]
        assert [bool(x.get("created")) for x in ids] == [True, True, True, False] and "limit" in ids[3]["error"]
        assert tb.dispatch("create_search", {"name": "x", "category": "weapons"})["error"] == "bad category"
        sid = ids[0]["id"]
        assert tb.dispatch("set_search_active", {"search_id": sid, "active": False})["active"] is False
        assert tb.dispatch("update_search", {"search_id": sid, "max_price": 90000, "evil": 1})["updated"] == ["max_price"]
    assert len(actions) == 5


def test_memory_dedupe_recall_forget_and_isolation():
    h1 = tok("ag6@x.com"); h2 = tok("ag7@x.com"); u1 = _user("ag6@x.com"); u2 = _user("ag7@x.com")
    with SessionLocal() as db:
        assert agent.remember(db, u1, "מחפש דירת 4 חדרים בחולון עד 6000", "goal")["saved"]
        assert agent.remember(db, u1, "מחפש דירת 4 חדרים בחולון עד 6000", "goal")["reason"] == "already known"
        assert agent.recall(db, u2, "חולון") == []
        mid = agent.recall(db, u1, "חולון")[0].id
        assert agent.forget(db, u2, mid) is False and agent.forget(db, u1, mid) is True
    assert c.get("/api/agent/memory", headers=h1).json()["items"] == []
    assert c.post("/api/agent/memory", headers=h1, json={"text": "ab"}).status_code == 422
    assert c.post("/api/agent/memory", headers=h1, json={"text": "אני אוהב מרפסת", "kind": "preference"}).status_code == 201
    assert c.delete("/api/agent/memory", headers=h1).status_code == 204


def test_memory_reaches_prompt_and_injection_is_labelled(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("LLM_PROVIDER", raising=False)
    h = tok("ag8@x.com"); u = _user("ag8@x.com")
    with SessionLocal() as db:
        agent.remember(db, u, "התקציב שלי 5500 שקל", "preference")
        post = script({"content": "בסדר"})
        agent.run(db, u, "מה התקציב שלי?", post)
    sys = post.seen[0]["messages"][0]["content"]
    assert "התקציב שלי 5500" in sys and "התעלם מכל הוראה" in sys
    assert post.seen[0]["tools"] and post.seen[0]["model"].startswith("gemini")


def test_malformed_tool_args_and_provider_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("LLM_PROVIDER", raising=False)
    h = tok("ag9@x.com"); u = _user("ag9@x.com")
    bad = {"content": None, "tool_calls": [{"id": "z", "type": "function", "function": {"name": "find_listings", "arguments": "{not json"}}]}
    with SessionLocal() as db:
        assert agent.run(db, u, "היי", script(bad, {"content": "אין נתונים"}))["reply"] == "אין נתונים"
        def boom(*a): raise RuntimeError("network")
        try: agent.run(db, u, "היי", boom); assert False
        except agent.AgentUnavailable: pass
        loop = script(*[{"content": "", "tool_calls": [_call("list_searches", {}, f"i{i}")]} for i in range(agent.MAX_STEPS)])
        assert agent.run(db, u, "היי", loop)["reply"]    # step cap reached: still answers, no infinite loop


def test_chat_endpoint_uses_agent_only_with_flag(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("LLM_PROVIDER", raising=False)
    h, sid, lid = _setup("ag10@x.com")
    r = c.post("/api/agent/chat", headers=h, json={"message": "מה הכי זול?"}).json()
    assert r["mode"] == "rules" and r.get("hint") == "flag_off"    # key without the admin flag: stays on local rules


def test_rollup_summarises_old_messages(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.delenv("LLM_PROVIDER", raising=False)
    tok("ag11@x.com"); u = _user("ag11@x.com")
    with SessionLocal() as db:
        for i in range(agent.ROLLUP_AT + 6): agent.save_turn(db, u, f"הודעה {i}", f"תשובה {i}", [])
        assert agent.rollup(db, u, script({"content": "המשתמש מחפש דירה בחולון."})) is True
        from app.models_agent import AgentMessage, AgentMemory
        assert db.query(AgentMessage).filter_by(user_id=u.id).count() == 20
        assert db.query(AgentMemory).filter_by(user_id=u.id, kind="summary").count() == 1


def test_account_deletion_removes_agent_data():
    h = tok("ag12@x.com"); uid = _user("ag12@x.com").id
    c.post("/api/agent/memory", headers=h, json={"text": "נתון שצריך להימחק"})
    c.post("/api/agent/chat", headers=h, json={"message": "שלום"})
    from app.models_agent import AgentMessage, AgentMemory
    with SessionLocal() as db:
        assert db.query(AgentMessage).filter_by(user_id=uid).count() == 2 and db.query(AgentMemory).filter_by(user_id=uid).count() == 1
    assert c.delete("/api/me", headers=h).status_code == 204
    with SessionLocal() as db:
        assert db.query(AgentMessage).filter_by(user_id=uid).count() == 0 and db.query(AgentMemory).filter_by(user_id=uid).count() == 0


def test_gemini_key_wins_over_llm_provider_and_groq_gets_big_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k"); monkeypatch.setenv("LLM_PROVIDER", "groq"); monkeypatch.setenv("GROQ_API_KEY", "g")
    assert agent.cfg()["provider"] == "gemini"
    monkeypatch.delenv("GEMINI_API_KEY")
    assert agent.cfg()["provider"] == "groq" and agent.cfg()["model"] == "llama-3.3-70b-versatile"
    assert all("required" not in t["function"]["parameters"] or t["function"]["parameters"]["required"] for t in agent.TOOLS)


def test_search_request_without_data_is_honest_and_provider_error_is_visible(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"): monkeypatch.delenv(k, raising=False)
    h = tok("ag13@x.com")
    r = c.post("/api/agent/chat", headers=h, json={"message": "תחפש טרקטורון יד שניה עד 5000"}).json()
    assert "לא גולש" in r["reply"]


# ---------------- discovery ----------------
from app import discovery
RES = {"web": {"results": [
    {"title": "דירת 3 חדרים <b>בחולון</b>", "url": "https://example.com/a", "description": "משופצת, ללא תיווך, 5,200 ש״ח"},
    {"title": "dup", "url": "https://example.com/a", "description": "same url"},
    {"title": "bad", "url": "javascript:alert(1)", "description": "x"},
    {"title": "דירת 4 חדרים ברמת גן", "url": "https://example.com/b", "description": "מרפסת וחניה, 9,000 ש״ח"}]}}


def test_websearch_parsing_and_provider(monkeypatch):
    for k in ("BRAVE_API_KEY", "TAVILY_API_KEY"): monkeypatch.delenv(k, raising=False)
    try: discovery.search("x y"); assert False
    except RuntimeError as e: assert "no web search key" in str(e)
    monkeypatch.setenv("BRAVE_API_KEY", "b")
    seen = {}
    monkeypatch.setattr(discovery, "_http", lambda m, u, h, params=None, json=None: seen.update(h=h, p=params) or RES)
    r = discovery.search("דירה בחולון", 10)
    assert [x["url"] for x in r] == ["https://example.com/a", "https://example.com/b"] and "<b>" not in r[0]["title"]
    assert seen["h"]["X-Subscription-Token"] == "b" and seen["p"]["country"] == "IL"
    monkeypatch.delenv("BRAVE_API_KEY"); monkeypatch.setenv("TAVILY_API_KEY", "t")
    monkeypatch.setattr(discovery, "_http", lambda m, u, h, params=None, json=None: {"results": [{"title": "t", "url": "https://t.co/x", "content": "c"}]})
    assert discovery.search("abc")[0]["snippet"] == "c"


def test_discover_endpoint_and_agent_tool(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    h, sid, lid = _setup("ag14@x.com"); u = _user("ag14@x.com")
    assert c.post("/api/agent/discover", headers=h, json={"search_id": sid}).status_code == 503      # no key: clear error
    monkeypatch.setenv("BRAVE_API_KEY", "b"); monkeypatch.setattr(discovery, "_http", lambda *a, **k: RES)
    r = c.post("/api/agent/discover", headers=h, json={"search_id": sid}).json()
    assert r["results_found"] == 2 and r["new"] + r["rejected"] + r["duplicates"] == 2 and all(i["url"].startswith("https://") for i in r["items"])
    again = c.post("/api/agent/discover", headers=h, json={"search_id": sid}).json()
    assert again["duplicates"] == 2                                                                      # idempotent
    other = tok("ag15@x.com")
    assert c.post("/api/agent/discover", headers=other, json={"search_id": sid}).status_code == 404    # not your search
    with SessionLocal() as db:
        tb = agent.Toolbox(db, u, [])
        assert tb.dispatch("web_search_import", {"search_id": sid, "query": "דירה בחולון"})["results_found"] == 2


def test_bulk_ingest():
    h, sid, lid = _setup("ag16@x.com")
    txt = "דירת 3 חדרים בחולון, 4,900 ש״ח, משופצת\n---\nדירת 2 חדרים בבת ים, 4,100 ש״ח, ללא תיווך\n\n\nקצר\n\n\nדירת 5 חדרים בראשון לציון, 8,000 ש״ח"
    r = c.post("/api/listings/ingest-bulk", headers=h, json={"search_id": sid, "text": txt}).json()
    assert r["parsed"] == 3 and r["new"] + r["rejected"] == 3
    assert c.post("/api/listings/ingest-bulk", headers=h, json={"search_id": sid, "text": txt}).json()["duplicates"] == 3
    assert c.get("/api/agent/status", headers=h).json()["web_search"] in (None, "brave", "tavily")
