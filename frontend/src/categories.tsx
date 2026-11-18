import { useMemo, useState } from "react";
import { CATALOG } from "./lib/catalog";
/** Grouped, searchable category picker with sub-category chips. Pure UI: the catalog is bundled, so it works offline. */
export function CategoryPicker({ value, sub, onChange, label = "קטגוריה" }: { value: string; sub?: string; onChange: (cat: string, sub: string) => void; label?: string }) {
  const [q, setQ] = useState(""), [open, setOpen] = useState(false);
  const cur = CATALOG.find(c => c.key === value);
  const groups = useMemo(() => {
    const term = q.trim().toLowerCase(), m = new Map<string, typeof CATALOG>();
    for (const c of CATALOG) {
      if (term && !(c.label.toLowerCase().includes(term) || c.key.includes(term) || c.group.includes(term) || c.subs.some(s => s[1].toLowerCase().includes(term)))) continue;
      m.set(c.group, [...(m.get(c.group) || []), c]);
    }
    return [...m.entries()];
  }, [q]);
  return <div className="catpick">
    <button type="button" className="catpick-cur ghost" aria-expanded={open} onClick={() => setOpen(!open)}>
      <span>{cur ? `${cur.icon} ${cur.label}` : `בחר ${label}`}</span><span className="faint">{CATALOG.length} קטגוריות ▾</span>
    </button>
    {open && <div className="catpick-pop card" role="listbox" aria-label={label}>
      <input autoFocus placeholder="חיפוש קטגוריה..." value={q} onChange={e => setQ(e.target.value)} />
      <div className="catpick-list">
        {groups.length === 0 && <div className="faint">לא נמצאה קטגוריה. נסו מילה אחרת.</div>}
        {groups.map(([g, items]) => <div key={g} className="catpick-group"><div className="catpick-gh">{g}</div>
          <div className="catpick-chips">{items.map(c => <button type="button" key={c.key} role="option" aria-selected={c.key === value} className={"cat-chip" + (c.key === value ? " on" : "")} onClick={() => { onChange(c.key, ""); if (!c.subs.length) setOpen(false); setQ(""); }}>{c.icon} {c.label}</button>)}</div></div>)}
      </div>
    </div>}
    {cur && cur.subs.length > 0 && <div className="catpick-subs" aria-label="תת-קטגוריה">
      <button type="button" className={"cat-chip sm" + (!sub ? " on" : "")} onClick={() => onChange(cur.key, "")}>הכול</button>
      {cur.subs.map(([k, l]) => <button type="button" key={k} className={"cat-chip sm" + (sub === k ? " on" : "")} onClick={() => { onChange(cur.key, k); setOpen(false); }}>{l}</button>)}
    </div>}
  </div>;
}
export const subLabel = (cat: string, sub: string) => CATALOG.find(c => c.key === cat)?.subs.find(s => s[0] === sub)?.[1] || "";
