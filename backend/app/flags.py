"""Runtime feature flags stored in system_settings (admin-toggleable). Optional paid features default OFF."""
import os, time
from .models2 import SystemSetting
DEFAULTS = {"llm_extraction": False, "pgvector": False, "maintenance_mode": False}
def _defaults() -> dict:
    """BRAINS_AUTO_ENABLE=1 switches the smart brain on by default (still overridable in the admin panel). Off unless you opt in,
    because enabling it sends listing text to the AI providers whose keys you configured."""
    return {**DEFAULTS, "llm_extraction": os.environ.get("BRAINS_AUTO_ENABLE") == "1"}
_c = {"t": 0.0, "v": dict(DEFAULTS)}
def load(db, force=False) -> dict:
    if not force and time.monotonic() - _c["t"] < 10: return _c["v"]
    row = db.get(SystemSetting, "flags"); v = {**_defaults(), **{k: bool(x) for k, x in (row.value if row else {}).items() if k in DEFAULTS}}
    _c["t"], _c["v"] = time.monotonic(), v; return v
def save(db, changes: dict) -> dict:
    bad = [k for k in changes if k not in DEFAULTS]
    if bad: raise ValueError("unknown flag: " + bad[0])
    cur = load(db, True); new = {**cur, **{k: bool(v) for k, v in changes.items()}}
    row = db.get(SystemSetting, "flags")
    if row: row.value = new
    else: db.add(SystemSetting(key="flags", value=new))
    db.commit(); return load(db, True)
