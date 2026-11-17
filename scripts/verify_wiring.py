#!/usr/bin/env python3
"""Wiring check (v3.16): every /api/... call the React app makes must exist as a route in the FastAPI app.

Usage (from the repository root):   python scripts/verify_wiring.py
Exit code 0 = everything the UI calls is served by the backend; 1 = at least one UI call has no matching route.
Also prints (informational only) backend routes the UI never calls, and routes grouped by module so a router that
silently failed to load (main.py loads the newer ones inside try/except) is visible here instead of in production.
Read-only: it imports the app with an in-memory database and never starts a server or touches your data.
"""
import os, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.environ.setdefault("JWT_SECRET", "wiring-check-" + "x" * 32)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(ROOT / "backend"))
from app import main as M  # noqa: E402

# ---- backend: path templates, "{param}" -> "{}"
routes: dict[str, set[str]] = {}
for r in M.app.routes:
    p = getattr(r, "path", None)
    if p and p.startswith("/api/"):
        routes.setdefault(re.sub(r"\{[^}]+\}", "{}", p), set()).update(getattr(r, "methods", None) or [])

# ---- frontend: string literals that start with /api/
LIT = re.compile(r"""["'`](/api/[^"'`\s]*)""")
calls: list[tuple[str, str, int]] = []
for f in sorted((ROOT / "frontend" / "src").rglob("*.ts*")):
    if f.name.endswith(".test.ts"): continue
    for i, line in enumerate(f.read_text(encoding="utf8").splitlines(), 1):
        line = re.sub(r"\$\{(?:[^{}]|\{[^{}]*\})*\}", "{}", line)   # ${ cond ? "a" : "b" } contains quotes: neutralise it first
        for m in LIT.finditer(line):
            raw = m.group(1).split("?")[0]
            calls.append((re.sub(r"\$\{[^}]*\}", "{}", raw), str(f.relative_to(ROOT)), i))


def matches(call: str) -> bool:
    prefix = call.endswith("/")                      # "/api/searches/" + id + "/report": literal is only the first part
    cs = [s for s in call.strip("/").split("/")]
    for tpl in routes:
        ts = tpl.strip("/").split("/")
        if prefix:
            if len(ts) > len(cs) and all(a == b or b == "{}" or a == "{}" for a, b in zip(cs, ts)): return True
        elif len(ts) == len(cs) and all(a == b or a == "{}" or b == "{}" for a, b in zip(cs, ts)): return True
    return False


missing = sorted({(c, f, n) for c, f, n in calls if not matches(c)})
used = {c for c, _, _ in calls}
unused = sorted(t for t in routes if not any(matches(c) and (c.strip("/").split("/")[:2] == t.strip("/").split("/")[:2]) and
                                              len(c.strip("/").split("/")) in (len(t.strip("/").split("/")),) or c.endswith("/") and t.startswith(c) for c in used))

by_mod: dict[str, int] = {}
for r in M.app.routes:
    mod = getattr(getattr(r, "endpoint", None), "__module__", "?").split(".")[-1]
    by_mod[mod] = by_mod.get(mod, 0) + 1

print(f"backend: {len(routes)} /api route templates | frontend: {len(calls)} /api call sites")
print("routes per module:", ", ".join(f"{k}={v}" for k, v in sorted(by_mod.items())))
expected = {"main", "routes_v2", "routes_v3", "routes_v4", "routes_v5", "routes_v6", "routes_v7", "routes_v8", "routes_v9"}
not_loaded = sorted(expected - set(by_mod))
if not_loaded: print("WARNING - router modules that did not register:", ", ".join(not_loaded))
if unused: print(f"info: {len(unused)} backend routes are API-only (not called by this UI), e.g. " + ", ".join(unused[:6]))
if missing:
    print("\nFAIL - UI calls without a backend route:")
    for c, f, n in missing: print(f"  {c}   ({f}:{n})")
if missing or not_loaded: sys.exit(1)
print("\nOK - every UI call is served by the backend and every router module is loaded.")
