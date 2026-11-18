import os, smtplib
from email.message import EmailMessage
import httpx

RESEND_URL = "https://api.resend.com/emails"


def configured() -> bool:
    """True when this server can send mail: Resend HTTPS API (works on Railway Trial/Hobby) or classic SMTP (Railway Pro and above)."""
    return bool(os.environ.get("RESEND_API_KEY") or os.environ.get("SMTP_HOST"))


def _from() -> str:
    return os.environ.get("MAIL_FROM") or os.environ.get("SMTP_FROM") or "Smart Sniper <no-reply@supercoder.agency>"


def _send_resend(to, subject, body, html):
    payload = {"from": _from(), "to": [to], "subject": subject, "text": body}
    if html: payload["html"] = html
    r = httpx.post(RESEND_URL, json=payload, headers={"Authorization": "Bearer " + os.environ["RESEND_API_KEY"]}, timeout=15)
    if r.status_code >= 300: raise RuntimeError("resend HTTP %s: %s" % (r.status_code, r.text[:300]))


def send_mail(to, subject, body, html=None):  # html (optional): adds an HTML alternative part; plain-text callers are unchanged
    if os.environ.get("RESEND_API_KEY"): return _send_resend(to, subject, body, html)   # HTTPS port 443: Railway never blocks it
    host = os.environ.get("SMTP_HOST")
    if not host: raise RuntimeError("mail not configured")
    m = EmailMessage(); m["From"] = _from(); m["To"] = to; m["Subject"] = subject; m.set_content(body)
    if html: m.add_alternative(html, subtype="html")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"): s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(m)
