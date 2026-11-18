import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CATALOG } from "./lib/catalog";
/** Grouped, searchable category picker with sub-category chips. Pure UI: the catalog is bundled, so it works offline.
 *  v12: the list is rendered in a portal attached to <body> and positioned against the trigger button, so it always opens ABOVE every
 *  card / stacking context (previously it opened underneath the content below it). On narrow screens it becomes a bottom sheet.
 *  Public API (props, exports) is unchanged. */
type Pos = { top: number; left: number; width: number; maxH: number; up: boolean; sheet: boolean };
export function CategoryPicker({ value, sub, onChange, label = "קטגוריה" }: { value: string; sub?: string; onChange: (cat: string, sub: string) => void; label?: string }) {
  const [q, setQ] = useState(""), [open, setOpen] = useState(false), [grp, setGrp] = useState("");
  const [pos, setPos] = useState<Pos | null>(null);
  const btn = useRef<HTMLButtonElement>(null), pop = useRef<HTMLDivElement>(null), uid = useId();
  const cur = CATALOG.find(c => c.key === value);
  const allGroups = useMemo(() => [...new Set(CATALOG.map(c => c.group))], []);
  const groups = useMemo(() => {
    const term = q.trim().toLowerCase(), m = new Map<string, typeof CATALOG>();
    for (const c of CATALOG) {
      if (grp && c.group !== grp) continue;
      if (term && !(c.label.toLowerCase().includes(term) || c.key.includes(term) || c.group.includes(term) || c.subs.some(s => s[1].toLowerCase().includes(term)))) continue;
      m.set(c.group, [...(m.get(c.group) || []), c]);
    }
    return [...m.entries()];
  }, [q, grp]);
  const total = groups.reduce((n, [, it]) => n + it.length, 0);

  const place = useCallback(() => {
    const el = btn.current; if (!el) return;
    const r = el.getBoundingClientRect(), vh = window.innerHeight, vw = window.innerWidth, sheet = vw < 640, gap = 6;
    if (sheet) { setPos({ top: 0, left: 0, width: vw, maxH: Math.round(vh * 0.82), up: false, sheet: true }); return; }
    const below = vh - r.bottom - gap - 12, above = r.top - gap - 12, up = below < 280 && above > below;
    const width = Math.max(r.width, Math.min(460, vw - 24)), left = Math.min(Math.max(12, r.right - width), vw - width - 12);
    setPos({ top: up ? r.top - gap : r.bottom + gap, left, width, maxH: Math.max(220, Math.min(480, up ? above : below)), up, sheet: false });
  }, []);
  useLayoutEffect(() => { if (open) place(); }, [open, place]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); btn.current?.focus(); } };
    const onDown = (e: MouseEvent | TouchEvent) => { const t = e.target as Node; if (!pop.current?.contains(t) && !btn.current?.contains(t)) setOpen(false); };
    window.addEventListener("resize", place); window.addEventListener("scroll", place, true);
    document.addEventListener("keydown", onKey); document.addEventListener("mousedown", onDown); document.addEventListener("touchstart", onDown);
    const lock = window.innerWidth < 640 ? document.body.style.overflow : null;
    if (lock !== null) document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true);
      document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); document.removeEventListener("touchstart", onDown);
      if (lock !== null) document.body.style.overflow = lock;
    };
  }, [open, place]);
  const close = () => { setOpen(false); setQ(""); setGrp(""); };
  const style: React.CSSProperties | undefined = pos ? (pos.sheet
    ? { insetInline: 0, insetBlockEnd: 0, maxBlockSize: pos.maxH }
    : { left: pos.left, inlineSize: pos.width, maxBlockSize: pos.maxH, ...(pos.up ? { bottom: window.innerHeight - pos.top } : { top: pos.top }) }) : undefined;

  return <div className="catpick">
    <button ref={btn} type="button" className="catpick-cur ghost" aria-expanded={open} aria-haspopup="listbox" aria-controls={uid} onClick={() => (open ? close() : setOpen(true))}>
      <span>{cur ? `${cur.icon} ${cur.label}` : `בחר ${label}`}</span><span className="faint">{CATALOG.length} קטגוריות {open ? "▴" : "▾"}</span>
    </button>
    {open && pos && createPortal(<>
      {pos.sheet && <div className="catpick-scrim" onClick={close} aria-hidden="true" />}
      <div ref={pop} id={uid} className={"catpick-pop card" + (pos.sheet ? " sheet" : "") + (pos.up ? " up" : "")} role="dialog" aria-label={label} style={style}>
        <div className="catpick-head">
          <input autoFocus placeholder="חיפוש קטגוריה..." value={q} onChange={e => setQ(e.target.value)} aria-label="חיפוש קטגוריה" />
          {pos.sheet && <button type="button" className="ghost catpick-x" onClick={close} aria-label="סגור">✕</button>}
        </div>
        <div className="catpick-tabs" role="tablist" aria-label="קבוצות">
          <button type="button" role="tab" aria-selected={!grp} className={"cat-chip sm" + (!grp ? " on" : "")} onClick={() => setGrp("")}>הכול</button>
          {allGroups.map(g => <button type="button" role="tab" aria-selected={grp === g} key={g} className={"cat-chip sm" + (grp === g ? " on" : "")} onClick={() => setGrp(grp === g ? "" : g)}>{g}</button>)}
        </div>
        <div className="catpick-list" role="listbox" aria-label={label}>
          {groups.length === 0 && <div className="faint catpick-empty">לא נמצאה קטגוריה. נסו מילה אחרת.</div>}
          {groups.map(([g, items]) => <div key={g} className="catpick-group"><div className="catpick-gh">{g} <span className="faint">· {items.length}</span></div>
            <div className="catpick-chips">{items.map(c => <button type="button" key={c.key} role="option" aria-selected={c.key === value} className={"cat-chip" + (c.key === value ? " on" : "")}
              onClick={() => { onChange(c.key, ""); if (!c.subs.length) close(); else { setQ(""); setGrp(""); } }}>{c.icon} {c.label}</button>)}</div></div>)}
        </div>
        <div className="catpick-foot faint">{total} קטגוריות{q ? ` תואמות "${q}"` : ""}{cur && cur.subs.length > 0 ? " · בחרו תת-קטגוריה למטה או לחצו הכול" : ""}</div>
        {cur && cur.subs.length > 0 && <div className="catpick-subs in" aria-label="תת-קטגוריה">
          <button type="button" className={"cat-chip sm" + (!sub ? " on" : "")} onClick={() => { onChange(cur.key, ""); close(); }}>הכול ב{cur.label}</button>
          {cur.subs.map(([k, l]) => <button type="button" key={k} className={"cat-chip sm" + (sub === k ? " on" : "")} onClick={() => { onChange(cur.key, k); close(); }}>{l}</button>)}
        </div>}
      </div>
    </>, document.body)}
    {cur && cur.subs.length > 0 && !open && <div className="catpick-subs" aria-label="תת-קטגוריה">
      <button type="button" className={"cat-chip sm" + (!sub ? " on" : "")} onClick={() => onChange(cur.key, "")}>הכול</button>
      {cur.subs.map(([k, l]) => <button type="button" key={k} className={"cat-chip sm" + (sub === k ? " on" : "")} onClick={() => onChange(cur.key, k)}>{l}</button>)}
    </div>}
  </div>;
}
export const subLabel = (cat: string, sub: string) => CATALOG.find(c => c.key === cat)?.subs.find(s => s[0] === sub)?.[1] || "";
