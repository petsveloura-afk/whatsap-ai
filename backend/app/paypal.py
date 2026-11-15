import os, httpx
def base(): return os.environ.get("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")
def configured(): return bool(os.environ.get("PAYPAL_CLIENT_ID") and os.environ.get("PAYPAL_SECRET"))
def plan_ids(): return {"pro": os.environ.get("PAYPAL_PLAN_PRO"), "vip": os.environ.get("PAYPAL_PLAN_VIP")}
def _hdr():
    r = httpx.post(base() + "/v1/oauth2/token", data={"grant_type": "client_credentials"}, auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_SECRET"]), timeout=15)
    r.raise_for_status(); return {"Authorization": "Bearer " + r.json()["access_token"]}
def create_subscription(plan_id, user_id, return_url, cancel_url):
    r = httpx.post(base() + "/v1/billing/subscriptions", headers=_hdr(), timeout=15, json={"plan_id": plan_id, "custom_id": user_id,
        "application_context": {"return_url": return_url, "cancel_url": cancel_url, "user_action": "SUBSCRIBE_NOW"}})
    r.raise_for_status(); d = r.json()
    return d["id"], next(l["href"] for l in d["links"] if l["rel"] == "approve")
def cancel_subscription(sub_id):
    httpx.post(f"{base()}/v1/billing/subscriptions/{sub_id}/cancel", headers=_hdr(), json={"reason": "User requested"}, timeout=15).raise_for_status()
def verify_webhook(h, event):
    if not (configured() and os.environ.get("PAYPAL_WEBHOOK_ID")): return False
    r = httpx.post(base() + "/v1/notifications/verify-webhook-signature", headers=_hdr(), timeout=15, json={
        "auth_algo": h.get("paypal-auth-algo"), "cert_url": h.get("paypal-cert-url"), "transmission_id": h.get("paypal-transmission-id"),
        "transmission_sig": h.get("paypal-transmission-sig"), "transmission_time": h.get("paypal-transmission-time"),
        "webhook_id": os.environ["PAYPAL_WEBHOOK_ID"], "webhook_event": event})
    return r.status_code == 200 and r.json().get("verification_status") == "SUCCESS"
