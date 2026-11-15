"""Official WhatsApp Business Cloud API only (no unofficial QR sessions). Business-initiated messages need an approved template (WHATSAPP_TEMPLATE)."""
import os, httpx
def configured(): return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))
def notify(to, text):
    msg = {"messaging_product": "whatsapp", "to": to}
    t = os.environ.get("WHATSAPP_TEMPLATE")
    if t: msg.update(type="template", template={"name": t, "language": {"code": os.environ.get("WHATSAPP_LANG", "he")}, "components": [{"type": "body", "parameters": [{"type": "text", "text": text[:500]}]}]})
    else: msg.update(type="text", text={"body": text[:1000]})
    httpx.post(f"https://graph.facebook.com/v20.0/{os.environ['WHATSAPP_PHONE_ID']}/messages", headers={"Authorization": "Bearer " + os.environ["WHATSAPP_TOKEN"]}, json=msg, timeout=8).raise_for_status()
