"""Sign-in/sign-up hardening: password policy, lockout, bot trap, forged tokens, CORS on errors."""
import datetime as dt, jwt, os, pytest
from tests.test_core import c, tok
from app import authsec
def _reg(email, pw="Correct-horse-42", **kw): return c.post("/api/auth/register", json={"email": email, "password": pw, **kw})
@pytest.fixture(autouse=True)
def clean():
    authsec.reset_state(); yield; authsec.reset_state()
def test_policy_endpoint():
    p = c.get("/api/auth/policy").json(); assert p["min_length"] == 10 and p["rules"]
@pytest.mark.parametrize("pw", ["password123", "1234567890", "aaaaaaaaaaaa", "abcdefghijkl"])
def test_weak_passwords_rejected_with_hebrew_reason(pw):
    r = _reg("weak@x.com", pw); assert r.status_code == 422 and r.json()["detail"], pw
def test_password_cannot_contain_email_name():
    assert _reg("danielcohen@x.com", "danielcohen-77").status_code == 422
def test_too_long_password_refused_not_truncated():
    assert _reg("long@x.com", "a1" * 40).status_code == 422
def test_register_login_and_duplicate():
    assert _reg("hard1@x.com").status_code == 201 and _reg("hard1@x.com").status_code == 409
    assert c.post("/api/auth/login", json={"email": "hard1@x.com", "password": "Correct-horse-42"}).status_code == 200
def test_bot_trap_pretends_success_but_creates_nothing():
    r = _reg("bot@x.com", website="http://spam"); assert r.status_code == 201
    assert c.post("/api/auth/login", json={"email": "bot@x.com", "password": "Correct-horse-42"}).status_code == 401
def test_lockout_after_failures_even_with_right_password():
    _reg("lock@x.com")
    for _ in range(authsec.LOCK_N): assert c.post("/api/auth/login", json={"email": "lock@x.com", "password": "wrong-password-1"}).status_code in (401, 429)
    r = c.post("/api/auth/login", json={"email": "lock@x.com", "password": "Correct-horse-42"}); assert r.status_code == 429 and "Retry-After" in r.headers
def test_unknown_account_same_answer_as_wrong_password():
    _reg("known@x.com")
    a = c.post("/api/auth/login", json={"email": "known@x.com", "password": "wrong-password-1"}); b = c.post("/api/auth/login", json={"email": "nobody@x.com", "password": "wrong-password-1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
def test_signup_rate_limit_per_ip(monkeypatch):
    monkeypatch.setenv("SIGNUP_LIMIT_PER_HOUR", "2")
    assert _reg("rl1@x.com").status_code == 201 and _reg("rl2@x.com").status_code == 201 and _reg("rl3@x.com").status_code == 429
def test_forged_and_foreign_tokens_rejected():
    ok = tok("tk@x.com"); uid = c.get("/api/auth/me", headers=ok).json()["id"]
    assert c.get("/api/auth/me", headers=ok).status_code == 200
    key, now = "x" * 40, dt.datetime.now(dt.timezone.utc)
    base = {"sub": uid, "iat": now, "exp": now + dt.timedelta(minutes=5), "iss": "smart-sniper", "aud": "smart-sniper-app", "typ": "access"}
    bad = {"wrong key": jwt.encode(base, "y" * 40, "HS256"), "expired": jwt.encode({**base, "exp": now - dt.timedelta(minutes=5)}, key, "HS256"),
           "wrong type": jwt.encode({**base, "typ": "refresh"}, key, "HS256"), "wrong aud": jwt.encode({**base, "aud": "other"}, key, "HS256"),
           "no iss": jwt.encode({k: v for k, v in base.items() if k != "iss"}, key, "HS256"), "legacy (no claims)": jwt.encode({"sub": uid, "exp": now + dt.timedelta(minutes=5)}, key, "HS256"),
           "alg none": jwt.encode(base, None, algorithm="none"), "garbage": "abc.def.ghi"}
    for name, t in bad.items(): assert c.get("/api/auth/me", headers={"Authorization": "Bearer " + t}).status_code == 401, name
def test_logout_all_revokes_refresh_tokens():
    _reg("la@x.com"); r = c.post("/api/auth/login", json={"email": "la@x.com", "password": "Correct-horse-42"}).json()
    h = {"Authorization": "Bearer " + r["access_token"]}
    assert c.post("/api/auth/logout-all", headers=h).status_code == 204
    assert c.post("/api/auth/refresh", json={"refresh_token": r["refresh_token"]}).status_code == 401
def test_cors_headers_on_errors_and_preflight(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com/"); o = {"Origin": "https://app.example.com"}
    r = c.post("/api/auth/login", json={"email": "nobody@x.com", "password": "wrong-password-1"}, headers=o); assert r.status_code == 401 and r.headers["access-control-allow-origin"] == "https://app.example.com"
    r = c.options("/api/auth/register", headers={**o, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}); assert r.status_code == 204 and r.headers["access-control-allow-origin"] == o["Origin"]
    assert "access-control-allow-origin" not in c.get("/api/health", headers={"Origin": "https://evil.example"}).headers
def test_cors_regex(monkeypatch):
    monkeypatch.setenv("CORS_ORIGIN_REGEX", r"https://[a-z0-9-]+\.vercel\.app")
    assert c.get("/api/health", headers={"Origin": "https://my-app-git-main.vercel.app"}).headers.get("access-control-allow-origin") == "https://my-app-git-main.vercel.app"
    assert "access-control-allow-origin" not in c.get("/api/health", headers={"Origin": "https://evil.com"}).headers

def test_client_ip_trusts_the_proxy_appended_entry_not_the_forged_one():
    class R:
        def __init__(s, h): s.headers = h; s.client = type("C", (), {"host": "10.0.0.1"})()
    assert authsec.client_ip(R({"x-forwarded-for": "6.6.6.6, 203.0.113.9"})) == "203.0.113.9"   # attacker prepended 6.6.6.6
    assert authsec.client_ip(R({})) == "10.0.0.1"
