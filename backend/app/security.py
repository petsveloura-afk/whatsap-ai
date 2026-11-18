import os, uuid, datetime as dt, bcrypt, jwt
SECRET = os.environ.get("JWT_SECRET", "")
ISSUER = "smart-sniper"
AUDIENCE = "smart-sniper-app"
def _secret():
    s = os.environ.get("JWT_SECRET", "")
    if len(s) < 32: raise RuntimeError("JWT_SECRET must be set (>=32 chars)")
    return s
def hash_pw(p: str) -> str: return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def check_pw(p: str, h: str) -> bool:
    try: return bcrypt.checkpw(p.encode()[:72], h.encode())
    except Exception: return False
def make_token(uid: str, minutes=30) -> str:
    """Access token. Besides sub/exp it now binds issuer, audience, type, issue time and a unique id, so a token minted for
    anything else (or by anyone without JWT_SECRET) is rejected by read_token."""
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({"sub": uid, "iat": now, "nbf": now - dt.timedelta(seconds=5), "exp": now + dt.timedelta(minutes=minutes),
                       "iss": ISSUER, "aud": AUDIENCE, "typ": "access", "jti": uuid.uuid4().hex}, _secret(), algorithm="HS256")
def read_token(t: str) -> str:
    p = jwt.decode(t, _secret(), algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER, leeway=10,
                   options={"require": ["exp", "sub", "iat", "iss", "aud"]})
    if p.get("typ") != "access" or not isinstance(p.get("sub"), str) or not p["sub"]: raise jwt.InvalidTokenError("wrong token type")
    return p["sub"]
