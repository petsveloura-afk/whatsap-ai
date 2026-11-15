"""Extra free Scout adapters (stdlib only). Same contract as scout.ADAPTERS: fn(text) -> [{title,text,link,id,image}].
Only publicly served structured data that site owners publish for machines (schema.org JSON-LD, CSV/JSON feeds, public
Telegram previews). robots.txt, SSRF guard and size limits are enforced by scout.fetch/handle_poll before parsing."""
import csv, io, json, re
from html.parser import HTMLParser
from . import scout

def _s(x): return scout._clean(str(x)) if x is not None else ""

# ---- schema.org JSON-LD (Product/Offer, RealEstateListing, ItemList, Vehicle ...) ----
class _LD(HTMLParser):
    def __init__(s): super().__init__(); s.on = False; s.buf = []; s.blocks = []
    def handle_starttag(s, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json": s.on = True; s.buf = []
    def handle_endtag(s, tag):
        if tag == "script" and s.on: s.on = False; s.blocks.append("".join(s.buf))
    def handle_data(s, d):
        if s.on: s.buf.append(d)

def _walk(node, out):
    if isinstance(node, list):
        for n in node: _walk(n, out)
    elif isinstance(node, dict):
        if "@graph" in node: _walk(node["@graph"], out)
        if "itemListElement" in node: _walk(node["itemListElement"], out)
        if "item" in node and isinstance(node["item"], dict): _walk(node["item"], out)
        t = node.get("@type"); t = " ".join(t) if isinstance(t, list) else str(t or "")
        if re.search(r"Product|Offer|RealEstateListing|Apartment|House|Vehicle|Car|Accommodation|Residence|Event|JobPosting", t): out.append(node)

def _price_text(n):
    o = n.get("offers") or n
    if isinstance(o, list): o = o[0] if o else {}
    if not isinstance(o, dict): return ""
    p, cur = o.get("price") or o.get("lowPrice"), str(o.get("priceCurrency") or "").upper()
    if p in (None, ""): return ""
    return f"{p} {'ש״ח' if cur in ('ILS', 'NIS') else cur}".strip()

def parse_jsonld(html: str) -> list[dict]:
    p = _LD(); p.feed(html); nodes = []
    for b in p.blocks:
        try: _walk(json.loads(b), nodes)
        except ValueError: continue
    out = []
    for n in nodes:
        img = n.get("image"); img = img[0] if isinstance(img, list) and img else img
        if isinstance(img, dict): img = img.get("url")
        extra = " ".join(_s(n.get(k)) for k in ("numberOfRooms", "floorSize") if n.get(k))
        addr = n.get("address")
        if not addr and isinstance(n.get("availableAtOrFrom"), dict): addr = n["availableAtOrFrom"].get("address")
        if isinstance(addr, dict): addr = " ".join(_s(addr.get(k)) for k in ("addressLocality", "streetAddress"))
        o = n.get("offers"); url = n.get("url") or (o.get("url") if isinstance(o, dict) else None)
        out.append({"title": _s(n.get("name")), "text": " ".join(x for x in (_s(n.get("description")), _s(addr), extra, _price_text(n)) if x),
                    "link": url, "id": _s(n.get("@id") or n.get("sku") or url), "image": img if isinstance(img, str) else None})
    return out

# ---- CSV (header: title,description,price,url,image[,currency]) ----
def parse_csv(txt: str) -> list[dict]:
    out = []
    for i, r in enumerate(csv.DictReader(io.StringIO(txt))):
        if i >= 500: break
        r = {(k or "").strip().lower(): v for k, v in r.items()}
        price = _s(r.get("price")); cur = _s(r.get("currency")).upper()
        price_t = f"{price} {'ש״ח' if cur in ('', 'ILS', 'NIS') else cur}" if price else ""
        out.append({"title": _s(r.get("title") or r.get("name")), "text": " ".join(x for x in (_s(r.get("description")), price_t) if x),
                    "link": r.get("url") or r.get("link") or None, "id": _s(r.get("id") or r.get("url")), "image": r.get("image") or None})
    return out

# ---- Reddit listing JSON (https://www.reddit.com/r/<sub>/new.json) ----
def parse_reddit(txt: str) -> list[dict]:
    data = json.loads(txt); out = []
    for ch in (data.get("data") or {}).get("children", []):
        d = ch.get("data") or {}
        thumb = d.get("thumbnail") if str(d.get("thumbnail", "")).startswith("https://") else None
        out.append({"title": _s(d.get("title")), "text": _s(d.get("selftext"))[:2000], "link": "https://www.reddit.com" + d["permalink"] if d.get("permalink") else None, "id": _s(d.get("id")), "image": thumb})
    return out

# ---- Public Telegram channel preview (https://t.me/s/<channel>) ----
class _TG(HTMLParser):
    def __init__(s): super().__init__(); s.depth = 0; s.cur = None; s.msgs = []; s.post = None
    def handle_starttag(s, tag, attrs):
        a = dict(attrs); c = a.get("class", "")
        if tag == "div" and "data-post" in a: s.post = a["data-post"]
        if tag == "div" and "tgme_widget_message_text" in c and s.cur is None: s.cur = []; s.depth = 1; s.msgs.append({"post": s.post, "parts": s.cur}); return
        if s.cur is not None and tag == "div": s.depth += 1
    def handle_endtag(s, tag):
        if s.cur is not None and tag == "div":
            s.depth -= 1
            if s.depth <= 0: s.cur = None
    def handle_data(s, d):
        if s.cur is not None: s.cur.append(d)
    def handle_startendtag(s, tag, attrs):
        if tag == "br" and s.cur is not None: s.cur.append(" ")

def parse_tg_public(html: str) -> list[dict]:
    p = _TG(); p.feed(html); out = []
    for m in p.msgs:
        t = _s(" ".join(m["parts"]))
        if len(t) >= 5: out.append({"title": t[:80], "text": t, "link": f"https://t.me/{m['post']}" if m["post"] else None, "id": m["post"] or "", "image": None})
    return out

EXTRA = {"jsonld": parse_jsonld, "csv": parse_csv, "reddit": parse_reddit, "tgpublic": parse_tg_public}
KINDS = ("rss", "jsonfeed") + tuple(EXTRA)
scout.ADAPTERS.update(EXTRA)  # additive registration; rss/jsonfeed untouched
