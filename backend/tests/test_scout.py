import pytest
from app import scout

def res(ip):
    return lambda host, port, type=None: [(2, 1, 6, "", (ip, port))]

def test_ssrf_blocks_private_and_odd_urls():
    for ip in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1", "0.0.0.0"):
        with pytest.raises(scout.UnsafeURL): scout.check_url("https://x.example/feed", res(ip))
    for bad in ("ftp://x.example/a", "file:///etc/passwd", "https://u:p@x.example/", "https://x.example:8080/"):
        with pytest.raises(scout.UnsafeURL): scout.check_url(bad, res("93.184.216.34"))
    assert scout.check_url("https://x.example/feed", res("93.184.216.34")) == "https://x.example/feed"

RSS = '<rss><channel><item><title>דירת 3 חדרים בחולון</title><description>&lt;b&gt;משופצת&lt;/b&gt; 5,200 ש"ח</description><link>https://x.example/1</link><guid>1</guid><enclosure url="https://x.example/i.jpg" type="image/jpeg"/></item></channel></rss>'
def test_parse_rss_and_text():
    it = scout.parse_rss(RSS)[0]
    assert it["link"] == "https://x.example/1" and it["image"] == "https://x.example/i.jpg" and "<b>" not in it["text"]
    assert "5,200" in scout.listing_text(it)

def test_xml_entity_bombs_rejected():
    with pytest.raises(ValueError): scout.parse_rss('<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><rss/>')

def test_jsonfeed():
    it = scout.parse_jsonfeed('{"items":[{"id":"1","title":"t","content_text":"iPhone 1,800 ש\\"ח","url":"https://x.example/a"}]}')[0]
    assert it["link"] == "https://x.example/a" and "1,800" in it["text"]

def test_robots():
    assert scout.robots_allows("https://x.example/feed", lambda u: None)
    assert not scout.robots_allows("https://x.example/feed", lambda u: "User-agent: *\nDisallow: /feed")
    assert scout.robots_allows("https://x.example/ok", lambda u: "User-agent: *\nDisallow: /feed")

class R:
    def __init__(s, code, headers=None, text=""): s.status_code, s.headers, s.text, s.content = code, headers or {}, text, text.encode()
    def raise_for_status(s):
        if s.status_code >= 400: raise RuntimeError(s.status_code)
def test_redirect_to_private_address_is_blocked(monkeypatch):
    calls = []
    def fake_check(url, resolver=None):
        if "internal" in url: raise scout.UnsafeURL("private")
        return url
    monkeypatch.setattr(scout, "check_url", fake_check)
    class C:
        def get(s, url, **k): calls.append(url); return R(302, {"location": "http://internal.local/x"})
    with pytest.raises(scout.UnsafeURL): scout.fetch("https://ok.example/f", C())
    assert calls == ["https://ok.example/f"]
