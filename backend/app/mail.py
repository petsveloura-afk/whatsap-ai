import os, smtplib
from email.message import EmailMessage
def send_mail(to, subject, body):
    host = os.environ.get("SMTP_HOST")
    if not host: raise RuntimeError("SMTP not configured")
    m = EmailMessage(); m["From"] = os.environ.get("SMTP_FROM", "no-reply@localhost"); m["To"] = to; m["Subject"] = subject; m.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"): s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(m)
