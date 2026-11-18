import os, re
os.environ["JWT_SECRET"] = "x" * 40
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["AUTO_CREATE_TABLES"] = "1"
os.environ.setdefault("SIGNUP_LIMIT_PER_HOUR", "100000")
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app import mail, emailverify
c = TestClient(app)
PW = "correct-horse-1"


class _Sync:   # run the mail thread inline so the test can read the link deterministically
    def __init__(self, target, daemon=None): self.t = target
    def start(self): self.t()


@pytest.fixture
def smtp(monkeypatch):
    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test"); monkeypatch.setenv("APP_URL", "https://app.test")
    monkeypatch.setattr(mail, "send_mail", lambda to, subj, body, html=None: sent.append((to, body)))
    monkeypatch.setattr(emailverify.threading, "Thread", _Sync)
    return sent


def _reg(email):
    assert c.post("/api/auth/register", json={"email": email, "password": PW}).status_code == 201
    t = c.post("/api/auth/login", json={"email": email, "password": PW}).json()["access_token"]
    return {"Authorization": "Bearer " + t}


def _token(sent):
    return re.search(r"verify=([\w-]+)", sent[-1][1]).group(1)


def test_without_smtp_nothing_is_required():
    h = _reg("ev-nosmtp@x.com"); me = c.get("/api/auth/me", headers=h).json()
    assert me["email_verified"] is True and me["verification_required"] is False


def test_register_sends_link_and_blocks_payment_until_verified(smtp):
    h = _reg("ev1@x.com")
    assert len(smtp) == 1 and smtp[0][0] == "ev1@x.com"
    me = c.get("/api/auth/me", headers=h).json(); assert me["email_verified"] is False and me["verification_required"] is True
    r = c.post("/api/billing/order", headers=h, json={"plan": "pro", "period": "monthly", "method": "paypal"})
    assert r.status_code in (403, 503)   # 503 when PayPal is not configured in CI; 403 once it is: never a paid order
    if r.status_code == 403: assert "אימות" in r.json()["detail"]
    assert c.post("/api/auth/verify-email", json={"token": _token(smtp)}).status_code == 200
    assert c.get("/api/auth/me", headers=h).json()["email_verified"] is True


def test_token_is_single_use_and_garbage_is_rejected(smtp):
    _reg("ev2@x.com"); t = _token(smtp)
    assert c.post("/api/auth/verify-email", json={"token": t}).status_code == 200
    assert c.post("/api/auth/verify-email", json={"token": t}).status_code == 400
    assert c.post("/api/auth/verify-email", json={"token": "x" * 40}).status_code == 400


def test_resend_invalidates_old_link_and_has_a_cooldown(smtp):
    h = _reg("ev3@x.com"); old = _token(smtp)
    assert c.post("/api/auth/resend-verification", headers=h).status_code == 202
    new = _token(smtp); assert new != old
    assert c.post("/api/auth/resend-verification", headers=h).status_code == 429   # 60 s cooldown
    assert c.post("/api/auth/verify-email", json={"token": old}).status_code == 400
    assert c.post("/api/auth/verify-email", json={"token": new}).status_code == 200
    assert c.post("/api/auth/resend-verification", headers=h).json()["already_verified"] is True


def test_admin_is_exempt(smtp, monkeypatch):
    monkeypatch.setenv("SUPER_ADMIN_EMAILS", "evboss@x.com")
    h = _reg("evboss@x.com"); assert c.get("/api/auth/me", headers=h).json()["email_verified"] is True
