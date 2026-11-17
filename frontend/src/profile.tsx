import { useEffect, useState } from "react";
import { Icon } from "./listings";
type Api = (path: string, o?: any) => Promise<any>;

/* ---------------------------------------------------------------- display + accessibility settings (this device only) */
export type Prefs = { text: "normal" | "large" | "xl"; contrast: "normal" | "high"; motion: "auto" | "reduce" };
const KEY = "sniper.display";
const ALLOWED: Record<keyof Prefs, string[]> = { text: ["normal", "large", "xl"], contrast: ["normal", "high"], motion: ["auto", "reduce"] };
export const DEFAULT_PREFS: Prefs = { text: "normal", contrast: "normal", motion: "auto" };

/** Reads the saved settings. Any storage problem (private mode, blocked storage, corrupt value) falls back to the defaults. */
export function loadPrefs(): Prefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "{}") || {};
    const out: any = { ...DEFAULT_PREFS };
    (Object.keys(ALLOWED) as (keyof Prefs)[]).forEach(k => { if (ALLOWED[k].includes(raw[k])) out[k] = raw[k]; });
    return out as Prefs;
  } catch { return { ...DEFAULT_PREFS }; }
}
/** Applies the settings as data-* attributes on <html> (styles.v3.5.css reacts to them) and remembers them. */
export function applyPrefs(p: Prefs, save = false) {
  const r = document.documentElement;
  r.dataset.text = p.text; r.dataset.contrast = p.contrast; r.dataset.motion = p.motion;
  if (save) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* storage unavailable: the setting still applies for this session */ } }
}

const ROLE_HE: Record<string, string> = { user: "משתמש", support: "תמיכה", admin: "מנהל", super_admin: "מנהל על" };
const PLAN_HE: Record<string, string> = { starter: "Starter", pro: "Pro", vip: "VIP" };
const CONF_HE: Record<string, string> = { none: "אין עדיין נתונים", low: "ביטחון נמוך", medium: "ביטחון בינוני", high: "ביטחון גבוה" };

function Seg({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange: (v: string) => void }) {
  return <div role="radiogroup" aria-label={label} className="pf-seg">
    {options.map(([v, t]) => <button key={v} type="button" role="radio" aria-checked={value === v} className="ghost sm" onClick={() => onChange(v)}>{t}</button>)}
  </div>;
}

/** Profile: who you are, how complete the account is, what the system learned about your taste, and display/accessibility settings.
 *  Talks to GET /api/profile and POST /api/profile/sync-memory (both new, both scoped to the logged-in user). */
export function ProfilePanel({ api, onNavigate }: { api: Api; onNavigate?: (tab: string) => void }) {
  const [p, setP] = useState<any>(null), [err, setErr] = useState(""), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false);
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [shown, setShown] = useState(0);

  const load = () => api("/api/profile").then(d => { setP(d); setErr(""); }).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  // the ring fills up after mount (CSS transition on --pf); reduced-motion users simply see the final value
  useEffect(() => { if (p) { const t = setTimeout(() => setShown(p.completeness.score), 60); return () => clearTimeout(t); } }, [p]);

  const sync = async () => {
    setBusy(true); setMsg(""); setErr("");
    try { const r = await api("/api/profile/sync-memory", { method: "POST" }); setMsg(r.message); await load(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const set = (k: keyof Prefs, v: string) => { const n = { ...prefs, [k]: v } as Prefs; setPrefs(n); applyPrefs(n, true); };

  if (!p) return <section className="pf-card" aria-label="פרופיל" aria-busy={!err}>{err ? <div className="err" role="alert">{err}</div> : <p className="faint">טוען פרופיל…</p>}</section>;
  const q = p.plan.max_searches, st = p.stats, ins = p.insights;
  const stat = (label: string, v: any) => <div className="pf-stat" key={label}><b>{v ?? "-"}</b><small>{label}</small></div>;

  return <section className="pf" aria-label="פרופיל">
    <div className="pf-card">
      <div className="pf-head">
        <div className="pf-avatar" aria-hidden="true">{p.user.initials}</div>
        <div className="pf-who">
          <b>{p.user.email}</b>
          <div className="pf-meta">
            <span className="pill on">{ROLE_HE[p.user.role] || p.user.role}</span>
            <span className="pill off">חבילה: {PLAN_HE[p.plan.id] || p.plan.id}</span>
            <span>{p.user.member_days === 0 ? "הצטרפת היום" : `חבר/ה כבר ${p.user.member_days} ימים`}</span>
          </div>
        </div>
        <div className="pf-score">
          <div className="pf-ring" style={{ "--pf": shown } as any} role="img" aria-label={`שלמות הפרופיל ${p.completeness.score} מתוך 100`}><b>{p.completeness.score}</b></div>
          <div><b>שלמות הפרופיל</b><div className="faint">{p.completeness.level}</div></div>
        </div>
      </div>
      {p.completeness.tips.length > 0 && <>
        <h3>הצעדים הבאים</h3>
        <ul className="pf-tips">{p.completeness.tips.map((t: any) => <li key={t.id}><span>{t.text}</span><span className="chip">+{t.points}</span>{onNavigate && <button type="button" className="ghost sm" onClick={() => onNavigate(t.tab)}>קח אותי לשם</button>}</li>)}</ul>
      </>}
    </div>

    <div className="pf-card">
      <h3>הפעילות שלך</h3>
      <div className="pf-stats">{[stat("חיפושים", st.searches), stat("מודעות", st.listings), stat("חדשות", st.new), stat("נשמרו", st.saved), stat("נוצר קשר", st.contacted), stat("נסגרו", st.purchased), stat("נדחו", st.rejected), stat("ציון ממוצע", st.avg_score), stat("ציון הכי גבוה", st.best_score)]}</div>
      {q != null
        ? <div><div className="pf-row"><span>מכסת חיפושים: {p.plan.searches_used} מתוך {q}</span></div>
            <div className="pf-bar" role="progressbar" aria-valuemin={0} aria-valuemax={q} aria-valuenow={Math.min(p.plan.searches_used, q)} aria-label="ניצול מכסת חיפושים"><i style={{ inlineSize: `${Math.min(100, (p.plan.searches_used / Math.max(1, q)) * 100)}%` }} /></div></div>
        : <div className="faint">אין מגבלת חיפושים לחשבון שלך.</div>}
    </div>

    <div className="pf-card">
      <h3>מה המערכת למדה עליך</h3>
      <p className="faint">נלמד רק ממה שבחרת בפועל (שמרת, יצרת קשר, דחית). {CONF_HE[ins.confidence]}.</p>
      {ins.statements.length > 0
        ? <ul className="pf-learned">{ins.statements.map((s: string, i: number) => <li key={i}>{s.replace(/^נלמד מהפעולות שלך:\s*/, "")}</li>)}</ul>
        : <div className="note">עוד אין מספיק מידע. שמור או דחה כמה מודעות, ומתי שיהיו לפחות שתיים דומות נוכל לזהות העדפה.</div>}
      <div className="pf-row">
        <button type="button" onClick={sync} disabled={busy || !p.memory.personalization}><Icon n="spark" /> סנכרן לזיכרון של הסוכן</button>
        <span className="faint">בזיכרון הסוכן: {p.memory.agent} פריטים ({p.memory.learned} נלמדו מהפעולות שלך)</span>
      </div>
      {!p.memory.personalization && <div className="note">ההתאמה האישית כבויה, ולכן לא נשמרים זיכרונות. אפשר להפעיל אותה בהגדרות הזיכרון למטה.</div>}
      <div aria-live="polite">{msg && <div className="ok">{msg}</div>}{err && <div className="err" role="alert">{err}</div>}</div>
    </div>

    <div className="pf-card">
      <h3>תצוגה ונגישות</h3>
      <p className="faint">ההגדרות נשמרות במכשיר הזה בלבד.</p>
      <div className="pf-set">
        <b id="pf-t">גודל טקסט</b><Seg label="גודל טקסט" value={prefs.text} onChange={v => set("text", v)} options={[["normal", "רגיל"], ["large", "גדול"], ["xl", "גדול מאוד"]]} />
        <b id="pf-c">ניגודיות</b><Seg label="ניגודיות" value={prefs.contrast} onChange={v => set("contrast", v)} options={[["normal", "רגילה"], ["high", "גבוהה"]]} />
        <b id="pf-m">אנימציות</b><Seg label="אנימציות" value={prefs.motion} onChange={v => set("motion", v)} options={[["auto", "לפי המכשיר"], ["reduce", "מופחתות"]]} />
      </div>
    </div>
  </section>;
}
