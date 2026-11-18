import { useEffect, useRef, useState } from "react";

/** Counts every in-flight API call; the thin bar at the top of the screen shows while any is pending. */
export function TopProgress() {
  const [on, setOn] = useState(false);
  useEffect(() => {
    let n = 0, t: any;
    const h = (e: any) => {
      n = Math.max(0, n + (e.detail || 0));
      clearTimeout(t);
      if (n > 0) t = setTimeout(() => setOn(true), 140);   // short calls never flicker the bar
      else setOn(false);
    };
    window.addEventListener("api-busy", h);
    return () => { window.removeEventListener("api-busy", h); clearTimeout(t); };
  }, []);
  return <div className={"v11-progress" + (on ? " on" : "")} aria-hidden="true"><i /></div>;
}

/** Shown while the saved session is being restored (instead of a blank screen). */
export function Splash() {
  return <div className="v11-splash" role="status" aria-live="polite">
    <div className="v11-splash-orb" aria-hidden="true" />
    <b>Smart Sniper AI</b>
    <span>טוען את המערכת…</span>
  </div>;
}

/** Number that eases from its previous value to the new one. Non-numbers render as-is. */
export function CountUp({ v }: { v: any }) {
  const [n, setN] = useState<number | null>(typeof v === "number" ? 0 : null);
  const prev = useRef(0);
  useEffect(() => {
    if (typeof v !== "number") { setN(null); return; }
    const calm = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (calm) { setN(v); prev.current = v; return; }
    const from = prev.current, t0 = performance.now(), dur = 700;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      setN(Math.round(from + (v - from) * e));
      if (p < 1) raf = requestAnimationFrame(tick); else prev.current = v;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [v]);
  return <>{n === null ? (v ?? "-") : n}</>;
}

export type PaletteItem = { id: string; label: string; hint?: string; nav?: boolean; run: () => void };

/** Quick switcher: Ctrl/Cmd+K (or "/") opens it, arrows + Enter choose, Esc closes. Alt+1..9 jumps straight to a menu section. */
export function CommandPalette({ items }: { items: PaletteItem[] }) {
  const [open, setOpen] = useState(false), [q, setQ] = useState(""), [i, setI] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = items.filter(x => !q.trim() || x.label.toLowerCase().includes(q.trim().toLowerCase()));
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const tag = ((e.target as HTMLElement)?.tagName || "").toLowerCase(), typing = tag === "input" || tag === "textarea" || tag === "select" || (e.target as HTMLElement)?.isContentEditable;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(o => !o); setQ(""); setI(0); return; }
      if (e.key === "/" && !typing && !open) { e.preventDefault(); setOpen(true); setQ(""); setI(0); return; }
      if (e.altKey && /^[1-9]$/.test(e.key)) { const nav = items.filter(x => x.nav)[Number(e.key) - 1]; if (nav) { e.preventDefault(); nav.run(); } }
    };
    const openEv = () => { setOpen(true); setQ(""); setI(0); };
    window.addEventListener("keydown", key); window.addEventListener("open-palette", openEv);
    return () => { window.removeEventListener("keydown", key); window.removeEventListener("open-palette", openEv); };
  }, [items, open]);
  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 30); }, [open]);
  if (!open) return null;
  const run = (x?: PaletteItem) => { if (!x) return; setOpen(false); x.run(); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") setOpen(false);
    else if (e.key === "ArrowDown") { e.preventDefault(); setI(v => Math.min(list.length - 1, v + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setI(v => Math.max(0, v - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); run(list[i]); }
  };
  return <div className="v11-cmd-back" onMouseDown={() => setOpen(false)} role="presentation">
    <div className="v11-cmd" role="dialog" aria-modal="true" aria-label="חיפוש מהיר" onMouseDown={e => e.stopPropagation()} onKeyDown={onKey}>
      <input ref={input} value={q} onChange={e => { setQ(e.target.value); setI(0); }} placeholder="לאן לעבור? הקלידו שם של מסך או פעולה…" aria-label="חיפוש מהיר" />
      <div className="v11-cmd-list" role="listbox">
        {list.length === 0 && <div className="v11-cmd-empty">לא נמצא כלום</div>}
        {list.map((x, k) => <button key={x.id} role="option" aria-selected={k === i} className={k === i ? "on" : ""} onMouseEnter={() => setI(k)} onClick={() => run(x)}><span>{x.label}</span>{x.hint && <kbd>{x.hint}</kbd>}</button>)}
      </div>
      <div className="v11-cmd-foot"><kbd>↑↓</kbd> ניווט <kbd>Enter</kbd> בחירה <kbd>Esc</kbd> סגירה</div>
    </div>
  </div>;
}
