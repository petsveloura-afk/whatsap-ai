"""Regenerates frontend/src/lib/catalog.ts from the backend registry. Run from the repo root: python scripts/gen_catalog.py"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app import categories as C
items = [{"key": k, "label": C.CATS[k]["label"], "group": C.CATS[k]["group"], "icon": C.CATS[k]["icon"], "subs": [[s["key"], s["label"]] for s in C.CATS[k]["subs"]]} for k in C.ORDER]
out = "// GENERATED from backend/app/categories.py (python scripts/gen_catalog.py). Offline fallback for the pickers: the UI works even if /api/categories is unreachable.\nexport type CatalogItem = { key: string; label: string; group: string; icon: string; subs: [string, string][] };\nexport const CATALOG: CatalogItem[] = %s;\n" % json.dumps(items, ensure_ascii=False, indent=1)
open(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "catalog.ts"), "w", encoding="utf-8").write(out)
print(len(items), "categories written")
