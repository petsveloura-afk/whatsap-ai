import os, re, time, httpx
def base(): return os.environ.get("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")
def configured(): return bool(os.environ.get("PAYPAL_CLIENT_ID") and os.environ.get("PAYPAL_SECRET"))
def plan_ids(): return {"pro": os.environ.get("PAYPAL_PLAN_PRO"), "vip": os.environ.get("PAYPAL_PLAN_VIP")}
_TOK: dict = {"key": None, "v": None, "exp": 0.0}
def reset_token_cache(): _TOK.update(key=None, v=None, exp=0.0)
def _hdr():
    """OAuth bearer. Cached per (base, client id) until 60 s before expiry, so one checkout is not 3 token round-trips."""
    key = (base(), os.environ["PAYPAL_CLIENT_ID"])
    if _TOK["key"] == key and _TOK["v"] and time.time() < _TOK["exp"] - 60: return {"Authorization": "Bearer " + _TOK["v"]}
    r = httpx.post(base() + "/v1/oauth2/token", data={"grant_type": "client_credentials"}, auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_SECRET"]), timeout=15)
    r.raise_for_status(); d = r.json()
    _TOK.update(key=key, v=d["access_token"], exp=time.time() + float(d.get("expires_in", 300)))
    return {"Authorization": "Bearer " + d["access_token"]}
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


# ======================================================================================================================
# v3.15: Orders v2 (one-time payments). Used for BOTH the PayPal button and PayPal "Card Fields" (card number typed into
# PayPal-hosted iframes: the card data never touches our servers, so we stay out of PCI scope beyond SAQ-A).
# ======================================================================================================================
ORDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")   # validate before putting an id into a PayPal URL path
class PayPalError(Exception):
    def __init__(self, status: int, issue: str = "", message: str = "", debug_id: str = ""):
        super().__init__(f"PayPal {status} {issue}: {message}"); self.status, self.issue, self.message, self.debug_id = status, issue or "", message or "", debug_id or ""
def _err(r) -> PayPalError:
    try: d = r.json()
    except Exception: d = {}
    det = (d.get("details") or [{}])[0] if isinstance(d.get("details"), list) and d.get("details") else {}
    return PayPalError(r.status_code, det.get("issue") or d.get("name") or "", det.get("description") or d.get("message") or "", d.get("debug_id") or r.headers.get("paypal-debug-id", ""))
def _call(method: str, path: str, body: dict | None = None, request_id: str | None = None):
    for attempt in (0, 1):
        h = {**_hdr(), "Content-Type": "application/json", "Prefer": "return=representation"}
        if request_id: h["PayPal-Request-Id"] = request_id   # idempotency: a retry can never create/capture/refund twice
        r = httpx.request(method, base() + path, headers=h, json=body, timeout=25)
        if r.status_code == 401 and attempt == 0: reset_token_cache(); continue   # token revoked/expired early: refresh once
        if r.status_code >= 400: raise _err(r)
        return r.json() if r.content else {}
def cards_enabled() -> bool: return configured() and os.environ.get("PAYPAL_CARDS_ENABLED", "1") != "0"
def is_live() -> bool: return "sandbox" not in base()
def public_config() -> dict:
    """Only values that are meant to be public (the client id is embedded in every PayPal checkout page by design). Never the secret."""
    return {"client_id": os.environ.get("PAYPAL_CLIENT_ID", "") if configured() else "", "env": "live" if is_live() else "sandbox",
            "currency": os.environ.get("BILLING_CURRENCY", "ILS"), "cards": cards_enabled()}
def create_order(amount: str, currency: str, custom_id: str, invoice_id: str, description: str, request_id: str, card: bool = False) -> str:
    body = {"intent": "CAPTURE", "purchase_units": [{"reference_id": "default", "custom_id": custom_id, "invoice_id": invoice_id,
            "description": description[:127], "amount": {"currency_code": currency, "value": amount}}]}
    if card:   # 3-D Secure only when the issuing bank requires it (SCA); PayPal runs the challenge inside its own iframe
        body["payment_source"] = {"card": {"attributes": {"verification": {"method": "SCA_WHEN_REQUIRED"}}}}
    return _call("POST", "/v2/checkout/orders", body, request_id)["id"]
def get_order(order_id: str) -> dict: return _call("GET", f"/v2/checkout/orders/{order_id}")
def capture_order(order_id: str, request_id: str) -> dict: return _call("POST", f"/v2/checkout/orders/{order_id}/capture", {}, request_id)
def refund_capture(capture_id: str, request_id: str, amount: str | None = None, currency: str | None = None, note: str = "") -> dict:
    body: dict = {}
    if amount and currency: body["amount"] = {"value": amount, "currency_code": currency}
    if note: body["note_to_payer"] = note[:255]
    return _call("POST", f"/v2/payments/captures/{capture_id}/refund", body, request_id)
# Hebrew, customer-safe explanations of the PayPal error codes a card payer can actually hit (never leak raw PayPal text to the UI)
DECLINE_HE = {
    "INSTRUMENT_DECLINED": "הכרטיס נדחה על ידי חברת האשראי. אפשר לנסות כרטיס אחר או לפנות לבנק.",
    "ORDER_NOT_APPROVED": "התשלום לא אושר. אפשר לנסות שוב.",
    "PAYER_ACTION_REQUIRED": "נדרש אימות נוסף מהבנק (3-D Secure). נסו שוב והשלימו את האימות.",
    "TRANSACTION_REFUSED": "העסקה נדחתה. אפשר לנסות כרטיס אחר.",
    "CARD_EXPIRED": "תוקף הכרטיס פג.",
    "INVALID_CARD_NUMBER": "מספר הכרטיס לא תקין.",
    "ORDER_ALREADY_CAPTURED": "התשלום כבר בוצע.",
}
def decline_message(e: "PayPalError") -> str: return DECLINE_HE.get(e.issue, "התשלום לא הושלם. לא חויבתם. אפשר לנסות שוב או לבחור אמצעי תשלום אחר.")
