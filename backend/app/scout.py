"""Scout source adapters (free). Only user-provided, publicly reachable feeds; no scraping of protected sites.
Safety: SSRF guard, robots.txt respected, size/time limits, no DTD/entity XML (billion-laughs safe)."""
import ipaddress, json, re, socket, urllib.parse, urllib.robotparser
import xml.etree.ElementTree as ET

MAX_BYTES = 1_000_000
UA = "SmartSniperBot/3.0 (+feed reader; respects robots.txt)"

class UnsafeURL(ValueError): pass

def check_url(url: str, resolver=socket.getaddrinfo) -> str:
    p = urllib.parse.urlsplit(url.strip())
    if p.scheme not in ("http", "https") or not p.hostname: raise UnsafeURL("only http(s) URLs are allowed")
    if p.username or p.password: raise UnsafeURL("credentials in URL are not allowed")
    if p.port not in (None, 80, 443): raise UnsafeURL("port not allowed")
    try: infos = resolver(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError: raise UnsafeURL("host cannot be resolved")
    for i in infos:
        ip = ipaddress.ip_address(i[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UnsafeURL("address is not publicly routable")
    return url.strip()

def robots_allows(url: str, fetch_text) -> bool:
    """fetch_text(robots_url)->str|None ; missing robots.txt means allowed."""
    p = urllib.parse.urlsplit(url); ru = f"{p.scheme}://{p.netloc}/robots.txt"
    txt = fetch_text(ru)
    if txt is None: return True
    rp = urllib.robotparser.RobotFileParser(); rp.parse(txt.splitlines())
    return rp.can_fetch(UA, url)

def fetch(url: str, client, depth: int = 0) -> str:
    """client: httpx.Client (injected so tests need no network). Redirects are re-validated."""
    check_url(url)
    r = client.get(url, headers={"User-Agent": UA}, follow_redirects=False, timeout=15)
    if r.status_code in (301, 302, 303, 307, 308) and depth < 3 and r.headers.get("location"):
        return fetch(urllib.parse.urljoin(url, r.headers["location"]), client, depth + 1)
    r.raise_for_status()
    if len(r.content) > MAX_BYTES: raise ValueError("feed too large")
    return r.text

def _clean(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()
def _local(tag): return tag.rsplit("}", 1)[-1]

def parse_rss(xml_text: str) -> list[dict]:
    if re.search(r"<!DOCTYPE|<!ENTITY", xml_text, re.I): raise ValueError("DTD/entities not allowed")
    root = ET.fromstring(xml_text); out = []
    for it in root.iter():
        if _local(it.tag) not in ("item", "entry"): continue
        d = {"title": "", "text": "", "link": None, "id": None, "image": None}
        for ch in it:
            n = _local(ch.tag)
            if n == "title": d["title"] = _clean(ch.text)
            elif n in ("description", "summary", "content"): d["text"] = _clean(ch.text)
            elif n == "link": d["link"] = ch.get("href") or _clean(ch.text) or d["link"]
            elif n in ("guid", "id"): d["id"] = _clean(ch.text)
            elif n in ("enclosure", "thumbnail", "content") and (ch.get("type", "image").startswith("image") or n == "thumbnail"): d["image"] = ch.get("url") or d["image"]
        out.append(d)
    return out

def parse_jsonfeed(txt: str) -> list[dict]:
    data = json.loads(txt)
    return [{"title": _clean(i.get("title")), "text": _clean(i.get("content_text") or i.get("content_html") or i.get("summary")),
             "link": i.get("url"), "id": str(i.get("id") or ""), "image": i.get("image")} for i in data.get("items", [])]

ADAPTERS = {"rss": parse_rss, "jsonfeed": parse_jsonfeed}

def listing_text(item: dict) -> str:
    return (item["title"] + ". " + item["text"]).strip(". ")[:5000]
