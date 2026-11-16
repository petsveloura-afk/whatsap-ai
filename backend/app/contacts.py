"""Contact details (v3.4): pulls the ways to reach a listing's owner out of the text that is ALREADY stored with the listing.
Pure functions, no network, no new tables. We only read what the owner published in the ad itself (phone, e-mail, WhatsApp / Telegram links)
plus the source link the search API returned, and hand them to the UI as one-tap actions (call / WhatsApp / e-mail / open source).
Nothing is fetched from the result page, so robots.txt and site terms are untouched."""
import re
from urllib.parse import urlparse

# Israeli mobile (05x), landline (02/03/04/08/09), virtual (07x) and +972 / 972 forms. Separators: space, dash, dot.
_PHONE = re.compile(
    r"(?<![\d.,/])"
    r"(?:\+?972[\s\-.]?\(?0?\)?[\s\-.]?|0)"
    r"(5\d|7\d|[2-4]|[89])"
    r"[\s\-.]?(\d{3})[\s\-.]?(\d{4}|\d{3})(?![\d])"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
_WA_HOSTS = ("wa.me", "api.whatsapp.com", "chat.whatsapp.com", "whatsapp.com")
_TG_HOSTS = ("t.me", "telegram.me")


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def normalize_phone(raw: str) -> str | None:
    """-> local Israeli format with a leading 0 (e.g. 0501234567), or None if it does not look like a real number."""
    d = _digits(raw)
    if d.startswith("972"): d = "0" + d[3:]
    if d.startswith("00972"): d = "0" + d[5:]
    if not d.startswith("0"): return None
    if len(d) == 10 and re.match(r"0(5\d|7\d)\d{7}$", d): return d
    if len(d) == 9 and re.match(r"0[2-489]\d{7}$", d): return d
    return None


def pretty_phone(local: str) -> str:
    if len(local) == 10: return f"{local[:3]}-{local[3:6]}-{local[6:]}"
    return f"{local[:2]}-{local[2:]}"


def intl(local: str) -> str:
    """0501234567 -> 972501234567 (the form wa.me and tel: expect)."""
    return "972" + local[1:]


def extract_contacts(text: str | None, source_url: str | None = None) -> dict:
    """-> {phones:[{display,tel,whatsapp}], emails:[...], whatsapp_links:[...], telegram_links:[...], source:{url,host}|None, has_direct:bool}"""
    t = text or ""
    phones, seen = [], set()
    for m in _PHONE.finditer(t):
        n = normalize_phone(m.group(0))
        if not n or n in seen: continue
        seen.add(n)
        mobile = n.startswith("05")
        phones.append({"display": pretty_phone(n), "tel": "+" + intl(n), "whatsapp": ("https://wa.me/" + intl(n)) if mobile else None, "mobile": mobile})
        if len(phones) >= 4: break
    emails = []
    for m in _EMAIL.finditer(t):
        e = m.group(0).strip(".").lstrip("-_%+").lower()
        if e not in emails: emails.append(e)
        if len(emails) >= 3: break
    wa, tg = [], []
    for m in _URL.finditer(t):
        u = m.group(0).rstrip(".,;:!?)")
        host = (urlparse(u).hostname or "").lower().removeprefix("www.")
        if host in _WA_HOSTS and u not in wa: wa.append(u[:300])
        elif host in _TG_HOSTS and u not in tg: tg.append(u[:300])
    source = None
    if source_url and re.match(r"^https?://", source_url):
        host = (urlparse(source_url).hostname or "").lower().removeprefix("www.")
        source = {"url": source_url[:1000], "host": host}
    return {"phones": phones, "emails": emails, "whatsapp_links": wa[:2], "telegram_links": tg[:2], "source": source,
            "has_direct": bool(phones or emails or wa or tg)}


def _lst(v) -> list:
    return [str(x)[:120] for x in v][:6] if isinstance(v, list) else []


def listing_card(l) -> dict:
    """Serialises a Listing row for the dashboard: everything the old endpoint returned (id, score, status, extracted, risks)
    plus the title/summary, source, contact actions and timestamps. Old keys are never removed or renamed."""
    from .relevance import gate
    raw = (l.raw_text or "").strip(); sd = l.score_detail if isinstance(l.score_detail, dict) else {}
    first = raw.split("\n", 1)[0].strip()
    g = gate(raw, l.source_url, l.extracted or {}) if l.status in ("new", "contacted") else None
    score, status = (min(l.score, g[0]), "rejected") if g and g[0] < 59 else (l.score, l.status)
    return {
        "id": l.id, "score": score, "status": status, "extracted": l.extracted, "risks": l.risks,
        "search_id": l.search_id, "title": first[:140], "summary": " ".join(raw.split())[:420], "raw_text": raw[:5000],
        "source_url": l.source_url, "contact": extract_contacts(raw, l.source_url),
        "note": l.note, "created_at": l.created_at.isoformat() if l.created_at else None,
        "highlights": _lst(sd.get("highlights")), "reasons": _lst([*(sd.get("rejection_reasons") or []), *([g[1]] if g else [])]), "label": sd.get("label"),
    }
