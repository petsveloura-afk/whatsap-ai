"""Sign-in / sign-up hardening (additive, no new tables): password policy, brute-force lockout, bot trap, per-IP signup limit.
State is in memory (correct for one instance; the shared DB limiter in main.limiter still applies on Postgres)."""
import os, re, time, threading, collections
COMMON = {"password", "password1", "password12", "password123", "1234567890", "12345678910", "0123456789", "qwertyuiop", "qwerty12345", "qwerty123456",
          "iloveyou12", "letmein123", "welcome123", "admin12345", "administrator", "abcdefghij", "abc1234567", "1q2w3e4r5t", "changeme123", "p@ssw0rd123",
          "passw0rd123", "000000000000", "111111111111", "aaaaaaaaaa", "israel12345", "shalom12345", "sniper12345", "smartsniper"}
MIN_LEN, MAX_BYTES = 10, 72
def _seq(p: str) -> bool:
    s = p.lower()
    if len(set(s)) <= 3: return True
    run = 1
    for a, b in zip(s, s[1:]):
        run = run + 1 if ord(b) - ord(a) in (1, -1) else 1
        if run >= 6: return True
    return False
def check_password(pw: str, email: str = "") -> tuple[bool, str]:
    """-> (ok, Hebrew reason). bcrypt only reads 72 bytes, so longer passwords are refused instead of silently truncated."""
    if len(pw) < MIN_LEN: return False, f"הסיסמה קצרה מדי: לפחות {MIN_LEN} תווים"
    if len(pw.encode()) > MAX_BYTES: return False, f"הסיסמה ארוכה מדי: עד {MAX_BYTES} בתים"
    if pw.strip() != pw: return False, "אין להתחיל או לסיים סיסמה ברווח"
    low = pw.lower()
    if low in COMMON or re.sub(r"\d+$", "", low) in COMMON: return False, "הסיסמה נפוצה מדי ולכן לא בטוחה. בחרו סיסמה ייחודית"
    if _seq(pw): return False, "הסיסמה מבוססת על רצף או תו חוזר. בחרו סיסמה פחות צפויה"
    local = (email or "").split("@")[0].lower()
    if len(local) >= 4 and local in low: return False, "הסיסמה לא יכולה להכיל את שם המשתמש של האימייל"
    if not (re.search(r"[A-Za-z\u05d0-\u05ea]", pw) and re.search(r"\d|[^\w\s]", pw)): return False, "הסיסמה צריכה לכלול אותיות וגם מספר או סימן"
    return True, ""
def strength(pw: str) -> int:
    s = 0
    s += min(len(pw), 16) * 4
    s += 10 * sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w\s]"))
    return max(0, min(100, s - (30 if pw.lower() in COMMON else 0)))
def policy() -> dict:
    return {"min_length": MIN_LEN, "max_bytes": MAX_BYTES, "lockout_attempts": LOCK_N, "lockout_minutes": LOCK_WINDOW // 60, "signups_per_hour_per_ip": _signup_n(),
            "rules": ["לפחות 10 תווים", "אותיות וגם מספר או סימן", "לא סיסמה נפוצה או רצף", "לא מבוססת על כתובת האימייל"]}
LOCK_N, LOCK_WINDOW = 8, 900
def _signup_n() -> int:
    try: return int(os.environ.get("SIGNUP_LIMIT_PER_HOUR", "8"))
    except ValueError: return 8
_lock = threading.Lock(); _fails: dict[str, collections.deque] = collections.defaultdict(collections.deque); _signups: dict[str, collections.deque] = collections.defaultdict(collections.deque)
def _prune(q, window, now):
    while q and now - q[0] > window: q.popleft()
def locked_for(email: str) -> int:
    """Seconds left on the lock for this account (0 = not locked). Keyed by email only, so rotating IPs does not help an attacker."""
    now = time.monotonic()
    with _lock:
        q = _fails[email]; _prune(q, LOCK_WINDOW, now)
        return int(LOCK_WINDOW - (now - q[0])) + 1 if len(q) >= LOCK_N else 0
def record_failure(email: str):
    with _lock: _fails[email].append(time.monotonic())
def record_success(email: str):
    with _lock: _fails.pop(email, None)
def signup_allowed(ip: str) -> bool:
    now = time.monotonic()
    with _lock:
        q = _signups[ip]; _prune(q, 3600, now)
        if len(q) >= _signup_n(): return False
        q.append(now); return True
def reset_state():   # tests only
    with _lock: _fails.clear(); _signups.clear()
def client_ip(request) -> str:
    """Real client address behind the host's proxy. X-Forwarded-For can be forged by the client, but the proxy APPENDS the address it saw,
    so with N trusted proxy hops (TRUSTED_PROXY_HOPS, default 1 = Railway/Render) the N-th entry from the right is the trustworthy one."""
    fwd = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
    try: hops = max(1, int(os.environ.get("TRUSTED_PROXY_HOPS", "1")))
    except ValueError: hops = 1
    if fwd: return fwd[-hops] if len(fwd) >= hops else fwd[0]
    return request.client.host if request.client else "?"
