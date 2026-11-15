import os, datetime as dt, bcrypt, jwt
SECRET = os.environ.get("JWT_SECRET", "")
def _secret():
    s = os.environ.get("JWT_SECRET", "")
    if len(s) < 32: raise RuntimeError("JWT_SECRET must be set (>=32 chars)")
    return s
def hash_pw(p: str) -> str: return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def check_pw(p: str, h: str) -> bool: return bcrypt.checkpw(p.encode(), h.encode())
def make_token(uid: str, minutes=30) -> str:
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return jwt.encode({"sub": uid, "exp": exp}, _secret(), algorithm="HS256")
def read_token(t: str) -> str:
    return jwt.decode(t, _secret(), algorithms=["HS256"])["sub"]
