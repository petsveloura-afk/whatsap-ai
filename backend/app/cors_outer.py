"""Outermost CORS layer. The existing CORSMiddleware sits *inside* the error/maintenance/edge middlewares, so any 429/500/503 produced by
them left the server without CORS headers and browsers reported only "Failed to fetch". This ASGI wrapper is added last (= outermost),
so every response, including crashes and preflights, carries the right headers.
Allowed: CORS_ORIGINS (trailing "/" ignored), APP_URL, CORS_ORIGIN_REGEX, and localhost dev ports."""
import os, re
DEV = {"http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://localhost:3000"}
def _norm(o: str) -> str: return o.strip().rstrip("/")
def allowed_origins() -> set[str]:
    out = {_norm(o) for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()}
    if os.environ.get("APP_URL", "").strip(): out.add(_norm(os.environ["APP_URL"]))
    return {o for o in out if o and o != "*"} | DEV
def origin_ok(origin: str) -> bool:
    if not origin: return False
    o = _norm(origin)
    if o in allowed_origins(): return True
    rx = os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    if rx:
        try: return re.fullmatch(rx, o) is not None
        except re.error: return False
    return False
class OuterCORS:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.app(scope, receive, send)
        hdrs = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        origin = hdrs.get("origin", ""); ok = origin_ok(origin)
        if ok and scope["method"] == "OPTIONS" and "access-control-request-method" in hdrs:
            h = [(b"access-control-allow-origin", origin.encode()), (b"vary", b"Origin"), (b"access-control-allow-methods", b"GET, POST, PUT, PATCH, DELETE, OPTIONS"),
                 (b"access-control-allow-headers", (hdrs.get("access-control-request-headers") or "authorization, content-type").encode()),
                 (b"access-control-max-age", b"600"), (b"content-length", b"0")]
            await send({"type": "http.response.start", "status": 204, "headers": h}); await send({"type": "http.response.body", "body": b""}); return
        async def wrap(msg):
            if ok and msg["type"] == "http.response.start":
                hs = [(k, v) for k, v in msg.get("headers", []) if k.lower() not in (b"access-control-allow-origin", b"access-control-expose-headers")]
                hs += [(b"access-control-allow-origin", origin.encode()), (b"access-control-expose-headers", b"X-Request-ID, Retry-After"), (b"vary", b"Origin")]
                msg = {**msg, "headers": hs}
            await send(msg)
        await self.app(scope, receive, wrap)
