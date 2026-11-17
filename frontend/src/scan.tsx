import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./listings";
import "./styles.scan.css";
type Api = (path: string, o?: any) => Promise<any>;

/** v3.14 Scan Center: deep scans that run as a background job (live progress), graded results, market read-out, history and engine health.
 *  Talks only to the new /api/scan/* endpoints. Everything else in the app is untouched. */
/** v3.15 memory: the Scan Center remembers the last depth, search and switches on this device (failsafe: any storage error falls back to the defaults). */
const PREF_KEY = "ss.scan.prefs";
const loadPrefs = (): any => { try { return JSON.parse(localStorage.getItem(PREF_KEY) || "{}") || {}; } catch { return {}; } };
const savePrefs = (p: any) => { try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch {} };
const nf = (n: any) => (typeof n === "number" ? Math.round(n).toLocaleString("he-IL") : n ?? "");
const GRADE_HE: Record<string, string> = { A: "מצוינת", B: "טובה", C: "בינונית", D: "חלשה" };
const PHASES: [string, string][] = [["search", "חיפוש במנועים"], ["analyze", "ניתוח ודירוג"], ["import", "ייבוא להזדמנויות"], ["done", "סיכום"]];
const IMP_HE: Record<string, string> = { new: "נוסף להזדמנויות", rejected: "נפסל בסינון", duplicate: "כבר קיים אצלך", news: "כתבה, לא מודעה", skipped: "קצר מדי", error: "שגיאה בייבוא" };
const DEPTH_ICON: Record<string, string> = { quick: "bolt", standard: "radar", deep: "layers", max: "star" };
const download = (name: string, mime: string, content: string) => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["\ufeff" + content], { type: mime })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); };
const csvOf = (items: any[]) => { const cols: [string, (i: any) => any][] = [["דירוג", i => i.grade], ["ציון", i => i.rank], ["כותרת", i => i.title], ["מחיר", i => i.price ?? ""], ["חדרים", i => i.rooms ?? ""], ["עיר", i => i.city ?? ""], ["אתר", i => i.site], ["קישור", i => i.url]];
  const q = (v: any) => `"${String(v).replace(/"/g, '""')}"`; return [cols.map(c => q(c[0])).join(","), ...items.map(i => cols.map(c => q(c[1](i))).join(","))].join("\n"); };

function Ring({ pct, label, sub }: { pct: number; label: string; sub?: string }) {
  return <div className="sc-ring" style={{ "--p": pct } as any} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div><b>{label}</b>{sub && <small>{sub}</small>}</div></div>;
}

function Progress({ job, onCancel }: { job: any; onCancel: () => void }) {
  const idx = Math.max(0, PHASES.findIndex(p => p[0] === job.phase));
  return <div className="card sc-live" aria-live="polite">
    <div className="sc-live-top">
      <Ring pct={job.pct || 0} label={(job.pct || 0) + "%"} sub={job.phase === "search" ? `${job.done}/${job.total}` : undefined} />
      <div className="sc-live-main">
        <h3>{job.status === "running" ? "הסריקה רצה עכשיו" : job.status === "cancelled" ? "הסריקה בוטלה" : job.status === "error" ? "הסריקה נכשלה" : "הסריקה הסתיימה"}</h3>
        <p className="faint">{job.search} · סריקה {({ quick: "מהירה", standard: "רגילה", deep: "עמוקה", max: "מקסימלית" } as any)[job.depth] || ""} · נמצאו עד כה {job.found || 0} תוצאות{job.unique ? ` (${job.unique} ייחודיות)` : ""}</p>
        <ol className="sc-steps">{PHASES.map(([k, t], i) => <li key={k} className={i < idx || job.status === "done" ? "done" : i === idx && job.status === "running" ? "now" : ""}><i />{t}</li>)}</ol>
      </div>
      {job.status === "running" && <button className="ghost sm" onClick={onCancel}><Icon n="x" /> בטל</button>}
    </div>
    {job.error && <div className="err" role="alert">{job.error}</div>}{job.note && <div className="faint">{job.note}</div>}
    <div className="sc-log">{(job.log || []).slice().reverse().map((l: any, i: number) => <span key={i} className={"sc-q" + (l.error ? " bad" : l.found ? " good" : "")} title={l.error || l.query}>
      <b>{l.error ? "✗" : l.found}</b>{l.site ? l.site : l.query.slice(0, 34)}{(l.engines || []).length > 0 && <small>{l.engines.join("+")}</small>}</span>)}</div>
  </div>;
}

function Check({ c }: { c: any }) { return <span className={"sc-chk " + (c.ok === true ? "y" : c.ok === false ? "n" : "u")} title={c.ok === null ? "לא מופיע בתקציר" : undefined}>{c.ok === true ? "✓" : c.ok === false ? "✗" : "?"} {c.label}</span>; }

function Item({ it }: { it: any }) {
  const ph = it.import?.contact?.phones?.[0], em = it.import?.contact?.emails?.[0];
  return <article className={"sc-item g" + it.grade}>
    <div className="sc-grade" title={`התאמה ${GRADE_HE[it.grade]} · ציון ${it.rank}`}><b>{it.grade}</b><small>{it.rank}</small></div>
    <div className="sc-body">
      <h4><a href={it.url} target="_blank" rel="noopener noreferrer nofollow">{it.title || it.url}</a></h4>
      <div className="sc-meta">
        <span className="tag">{it.site}</span>
        {it.price != null && <span className="tag price">{nf(it.price)} {it.currency === "USD" ? "$" : "₪"}</span>}
        {it.rooms != null && <span className="tag">{it.rooms} חד׳</span>}{it.city && <span className="tag">{it.city}</span>}{it.sqm && <span className="tag">{it.sqm} מ״ר</span>}
        {(it.features || []).map((f: string) => <span className="tag" key={f}>{f}</span>)}
        {it.hits > 1 && <span className="tag good" title="כמה שאילתות ומנועים החזירו את אותה מודעה">{it.hits} מופעים</span>}
        {it.urgent && <span className="tag good">דחוף</span>}{(it.flags || []).map((f: string) => <span className="risk" key={f}>⚠ {f}</span>)}
      </div>
      {it.snippet && <p className="sc-snip">{it.snippet}</p>}
      <div className="sc-foot">
        {(it.checks || []).map((c: any) => <Check key={c.k} c={c} />)}
        {it.import && <span className={"status " + (it.import.status === "new" ? "new" : it.import.status === "rejected" ? "rejected" : "")}>{IMP_HE[it.import.status] || it.import.status}{it.import.score != null ? ` · ${it.import.score}%` : ""}</span>}
        <span className="sc-act">
          {ph && <a className="btn call sm" href={"tel:" + ph.tel}><Icon n="phone" />התקשר</a>}
          {ph?.whatsapp && <a className="btn wa sm" href={ph.whatsapp} target="_blank" rel="noopener noreferrer"><Icon n="chat" />וואטסאפ</a>}
          {em && <a className="btn mail sm" href={"mailto:" + em}><Icon n="mail" />אימייל</a>}
          <a className="btn src sm" href={it.url} target="_blank" rel="noopener noreferrer nofollow"><Icon n="link" />מקור</a>
        </span>
      </div>
    </div>
  </article>;
}

function Bars({ rows, unit }: { rows: [string, number][]; unit?: string }) {
  const mx = Math.max(1, ...rows.map(r => r[1]));
  return <div className="sc-bars">{rows.map(([k, v]) => <div key={k}><span>{k}</span><i><u style={{ inlineSize: (v / mx) * 100 + "%" }} /></i><b>{v}{unit}</b></div>)}</div>;
}

function Result({ r }: { r: any }) {
  const [g, setG] = useState<string>("all"), [sort, setSort] = useState("rank"), [q, setQ] = useState(""), [onlyPhone, setOnlyPhone] = useState(false), [onlyNew, setOnlyNew] = useState(false), [more, setMore] = useState(24);
  const items = useMemo(() => {
    let a = (r.items || []).filter((i: any) => (g === "all" || i.grade === g) && (!onlyPhone || i.phones > 0 || i.import?.contact?.phones?.length) && (!onlyNew || i.import?.status === "new") && (!q || (i.title + " " + i.snippet + " " + i.site).toLowerCase().includes(q.toLowerCase())));
    const by: any = { rank: (x: any, y: any) => y.rank - x.rank, price_asc: (x: any, y: any) => (x.price ?? 1e12) - (y.price ?? 1e12), price_desc: (x: any, y: any) => (y.price ?? -1) - (x.price ?? -1), hits: (x: any, y: any) => y.hits - x.hits };
    return [...a].sort(by[sort]);
  }, [r, g, sort, q, onlyPhone, onlyNew]);
  const mk = r.market || {}, cov = r.coverage || {}, imp = r.import || {};
  const kp: [string, any, string][] = [["תוצאות שנמצאו", r.found, "var(--cy)"], ["אחרי סינון", r.kept, "var(--vi)"], ["התאמות מצוינות", r.grades?.A ?? 0, "var(--gr)"], ["נוספו להזדמנויות", imp.new ?? 0, "var(--pk)"], ["זמן סריקה", (r.seconds ?? 0) + " ש׳", "var(--am)"]];
  return <div className="sc-res">
    <div className="sc-kpis">{kp.map(([k, v, c]) => <div className="kpi" key={k} style={{ "--k": c } as any}><span>{k}</span><b>{v}</b></div>)}</div>
    <div className="sc-cols">
      <div className="card"><h3>מה גילינו</h3>
        {(r.insights || []).map((x: any, i: number) => <div key={i} className={"sc-ins " + x.level}><b className="sc-ico" aria-hidden="true">{x.level === "good" ? "✓" : x.level === "warn" ? "!" : "i"}</b><span>{x.text}</span></div>)}
        {r.ai_brief && <div className="sc-brief"><b><Icon n="bot" /> תובנות AI</b><p>{r.ai_brief.text}</p></div>}
        <div className="sc-grades" aria-label="התפלגות דירוגים">{["A", "B", "C", "D"].map(k => <button key={k} className={"g" + k} aria-pressed={g === k} onClick={() => setG(g === k ? "all" : k)}><b>{r.grades?.[k] ?? 0}</b><small>{GRADE_HE[k]}</small></button>)}</div>
      </div>
      <div className="card"><h3>שוק ומחירים</h3>
        {mk.enough ? <><div className="sc-mk"><div><small>חציון</small><b>{nf(mk.median)} ₪</b></div><div><small>טווח</small><b>{nf(mk.min)}–{nf(mk.max)}</b></div><div><small>רבעון תחתון</small><b>{nf(mk.p25)}</b></div></div>
          {mk.deals?.length > 0 && <><small className="faint">מתחת לחציון ב-12%+ (התאמה גבוהה)</small>{mk.deals.map((d: any) => <a key={d.url} className="sc-deal" href={d.url} target="_blank" rel="noopener noreferrer nofollow"><b>-{d.below_pct}%</b><span>{d.title}</span><em>{nf(d.price)} ₪</em></a>)}</>}</>
          : <p className="faint">אין מספיק תוצאות עם מחיר כדי לחשב שוק ({mk.n ?? 0} מתוך 3 לפחות).</p>}
        <h4>מקורות</h4><Bars rows={cov.sites || []} />
        <details><summary>כיסוי לפי מנוע וזווית חיפוש</summary><Bars rows={cov.engines || []} /><Bars rows={(cov.by_angle || []).map(([k, v]: any) => [({ core: "ראשית", price: "מחיר", wording: "ניסוח", owner: "מבעלים", english: "אנגלית", site: "אתר", feature: "מאפיין", rooms: "חדרים" } as any)[k] || k, v])} /></details>
      </div>
    </div>
    <div className="sc-tools card">
      <div className="seg" role="group" aria-label="סינון לפי דירוג">{[["all", "הכול"], ["A", "A"], ["B", "B"], ["C", "C"], ["D", "D"]].map(([k, t]) => <button key={k} aria-pressed={g === k} onClick={() => setG(k)}>{t}</button>)}</div>
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="חיפוש בתוצאות" aria-label="חיפוש בתוצאות" />
      <select value={sort} onChange={e => setSort(e.target.value)} aria-label="מיון"><option value="rank">מיון: ציון</option><option value="price_asc">מחיר: נמוך לגבוה</option><option value="price_desc">מחיר: גבוה לנמוך</option><option value="hits">מספר מופעים</option></select>
      <label className="sc-sw"><input type="checkbox" checked={onlyPhone} onChange={e => setOnlyPhone(e.target.checked)} /> עם טלפון</label>
      <label className="sc-sw"><input type="checkbox" checked={onlyNew} onChange={e => setOnlyNew(e.target.checked)} /> חדשות בלבד</label>
      <button className="ghost sm" onClick={() => download(`scan-${(r.at || "").slice(0, 10)}.csv`, "text/csv;charset=utf-8", csvOf(items))}><Icon n="download" /> ייצוא CSV ({items.length})</button>
    </div>
    {items.length === 0 && <div className="empty-big"><div className="orb" aria-hidden="true" /><h3>אין תוצאות בסינון הזה</h3><p>נקה את המסננים או הרץ סריקה עמוקה יותר.</p></div>}
    <div className="sc-list">{items.slice(0, more).map((it: any) => <Item key={it.url} it={it} />)}</div>
    {items.length > more && <button className="ghost" onClick={() => setMore(more + 24)}>הצג עוד ({items.length - more})</button>}
    <details className="card"><summary>דוח מלא לכל שאילתה ({(r.report || []).length})</summary><table><thead><tr><th>שאילתה</th><th>אתר</th><th>תוצאות</th><th>מנועים</th><th>זמן</th></tr></thead><tbody>{(r.report || []).map((x: any, i: number) => <tr key={i}><td>{x.query}</td><td>{x.site || "כללי"}</td><td>{x.error ? <span className="err">✗ {x.error}</span> : x.found}</td><td>{(x.engines || []).join(", ")}</td><td>{x.ms}ms</td></tr>)}</tbody></table></details>
  </div>;
}

function Engines({ api, isAdmin }: { api: Api; isAdmin: boolean }) {
  const [d, setD] = useState<any>(null), [t, setT] = useState<any>(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const load = () => api("/api/scan/engines").then(setD).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  const test = async () => { try { setBusy(true); setErr(""); setT((await api("/api/scan/engines/test", { method: "POST" })).engines); load(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  if (!d) return <div className="skel" style={{ blockSize: 100 }} />;
  return <div className="sc-eng">
    <div className="kvs sc-kv"><div className="kv hl"><small>מנועים פעילים</small><b>{d.configured.join(", ") || "אין"}</b></div><div className="kv"><small>שאילתות חינם בחודש (הערכה)</small><b>{nf(d.est_free_queries_per_month)}</b></div><div className="kv"><small>סריקות מלאות בחודש</small><b>{nf(d.est_scans_per_month)}</b></div></div>
    <div className="sc-engs">{d.engines.map((e: any) => { const tr = Array.isArray(t) ? t.find((x: any) => x.name === e.name) : null; return <div key={e.name} className={"sc-e" + (e.configured ? " on" : "")}>
      <b>{e.name}</b><span className={"status " + (e.configured ? "new" : "")}>{e.configured ? `${e.keys} מפתחות` : "לא מוגדר"}</span>
      {e.configured && <small className="faint">{e.ok} הצלחות · {e.fail} כשלונות{e.avg_ms ? ` · ${Math.round(e.avg_ms)}ms` : ""}{e.keys_cooling ? ` · ${e.keys_cooling} נחים` : ""}</small>}
      {!e.configured && <small className="faint">{e.note} <a href={e.signup} target="_blank" rel="noopener noreferrer">הרשמה</a> · משתנה: <code>{e.env.join(", ")}</code></small>}
      {e.last_error && <small className="err">{e.last_error}</small>}
      {tr && <span className={tr.ok ? "ok" : "err"}>{tr.ok ? `✓ עובד (${tr.results} תוצאות, ${tr.ms}ms)` : `✗ ${tr.error}`}</span>}</div>; })}</div>
    {(d.advice || []).map((a: string, i: number) => <div className="sig" key={i}>💡 {a}</div>)}
    {isAdmin && <button className="ghost" onClick={test} disabled={busy}><Icon n="bolt" /> {busy ? "בודק..." : "בדוק חיבור חי לכל מנוע"}</button>}
    {err && <div className="err" role="alert">{err}</div>}
  </div>;
}

export function ScanCenter({ api, searches = [], isAdmin = false, onChanged, goTab }: { api: Api; searches?: any[]; isAdmin?: boolean; onChanged?: () => void; goTab?: (t: string) => void }) {
  const [view, setView] = useState("scan"), [sid, setSid] = useState<string>(() => loadPrefs().sid || ""), [depth, setDepth] = useState<string>(() => (["quick", "standard", "deep", "max"].includes(loadPrefs().depth) ? loadPrefs().depth : "standard")), [q, setQ] = useState(""), [imp, setImp] = useState<boolean>(() => loadPrefs().imp !== false), [ai, setAi] = useState<boolean>(() => loadPrefs().ai !== false);
  const [depths, setDepths] = useState<any[]>([]), [plan, setPlan] = useState<any>(null), [job, setJob] = useState<any>(null), [res, setRes] = useState<any>(null), [hist, setHist] = useState<any[]>([]), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const timer = useRef<any>(null), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; clearTimeout(timer.current); }; }, []);
  useEffect(() => { if (searches.length && !searches.some((s: any) => s.id === sid)) setSid(searches[0]?.id || ""); }, [searches]);
  useEffect(() => { if (sid) savePrefs({ sid, depth, imp, ai }); }, [sid, depth, imp, ai]);
  const loadHist = useCallback(() => api("/api/scan/history").then(d => setHist(d.items || [])).catch(() => {}), []);
  const poll = useCallback((id: string) => {
    clearTimeout(timer.current);
    const tick = async () => {
      try {
        const j = await api("/api/scan/jobs/" + id); if (!alive.current) return; setJob(j);
        if (j.status === "running") timer.current = setTimeout(tick, 1100);
        else { if (j.result) { setRes(j.result); onChanged?.(); } loadHist(); }
      } catch (e: any) { if (alive.current) { setJob((p: any) => p ? { ...p, status: "error", error: e.message } : p); } }
    };
    tick();
  }, []);
  useEffect(() => {
    api("/api/scan/depths").then(d => setDepths(d.depths)).catch(() => {}); loadHist();
    api("/api/scan/active").then(d => { if (d.job) { setJob(d.job); poll(d.job.id); } else api("/api/scan/last").then(l => l.result && setRes(l.result)).catch(() => {}); }).catch(() => {});
  }, []);
  const body = () => ({ search_id: sid, depth, query: q.trim() || null, import_results: imp, ai_brief: ai });
  const preview = async () => { try { setErr(""); setBusy(true); setPlan(await api("/api/scan/preview", { method: "POST", body: body() })); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const start = async () => { try { setErr(""); setBusy(true); setPlan(null); setRes(null); const r = await api("/api/scan/start", { method: "POST", body: body() }); setJob({ id: r.id, status: "running", phase: "queued", pct: 0, done: 0, total: 0, found: 0, depth, search: searches.find((s: any) => s.id === sid)?.name, log: [] }); setView("scan"); poll(r.id); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const cancel = async () => { try { await api(`/api/scan/jobs/${job.id}/cancel`, { method: "POST" }); } catch (e: any) { setErr(e.message); } };
  const running = job?.status === "running"; const cur = depths.find(d => d.id === depth);
  return <div className="sc">
    <div className="pro-hero sc-hero"><h3>מרכז סריקות</h3><p>סריקה עמוקה שרצה ברקע: עד 30 ניסוחים במקביל, כמה מנועי חיפוש יחד, ניתוח וציון לכל תוצאה, סינון זבל וכפילויות, וייבוא אוטומטי להזדמנויות. אפשר לעבור לשונית אחרת והסריקה ממשיכה.</p></div>
    <div className="seg" role="tablist" aria-label="מרכז סריקות">{[["scan", "סריקה ותוצאות", "radar"], ["history", "היסטוריה", "layers"], ["engines", "מנועי חיפוש", "bolt"]].map(([k, t, ic]) => <button key={k} role="tab" aria-pressed={view === k} onClick={() => { setView(k); if (k === "history") loadHist(); }}><Icon n={ic} />{t}</button>)}</div>
    {view === "scan" && <>
      <div className="card sc-form">
        {searches.length === 0 ? <div className="empty-big"><div className="orb" aria-hidden="true" /><h3>עוד אין חיפוש לסרוק</h3><p>צור חיפוש בלשונית "חיפושים ומקורות" (מה מחפשים, אזור ותקציב) ואז חזור לכאן.</p>{goTab && <button onClick={() => goTab("discover")}><Icon n="radar" /> ליצירת חיפוש</button>}</div> : <>
          <div className="pro-form"><label>חיפוש<select value={sid} onChange={e => { setSid(e.target.value); setPlan(null); }}>{searches.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
            <label>שאילתה חופשית (אופציונלי)<input value={q} maxLength={200} onChange={e => { setQ(e.target.value); setPlan(null); }} placeholder="למשל: דירת 4 חדרים ברמת גן עם חניה" /></label></div>
          <div className="sc-depths" role="radiogroup" aria-label="עומק סריקה">{(depths.length ? depths : [{ id: "standard", label: "רגילה", queries: 12, fanout: 2, desc: "" }]).map((d: any) => <button key={d.id} role="radio" aria-checked={depth === d.id} className={"sc-depth" + (depth === d.id ? " on" : "")} onClick={() => { setDepth(d.id); setPlan(null); }}>
            <Icon n={DEPTH_ICON[d.id] || "radar"} /><b>{d.label}</b><small>{d.queries} שאילתות · {d.fanout} מנועים</small></button>)}</div>
          {cur && <p className="faint">{cur.desc}</p>}
          <div className="rowf"><label className="sc-sw"><input type="checkbox" checked={imp} onChange={e => setImp(e.target.checked)} /> ייבא את הטובות להזדמנויות</label><label className="sc-sw"><input type="checkbox" checked={ai} onChange={e => setAi(e.target.checked)} /> תובנות AI (אם הסוכן החכם פעיל)</label></div>
          <div className="rowf"><button className="ghost" disabled={busy || running || !sid} onClick={preview}><Icon n="eye" /> תצוגה מקדימה (בלי עלות)</button><button disabled={busy || running || !sid} onClick={start}><Icon n="radar" /> {running ? "סריקה רצה..." : "הפעל סריקה"}</button></div>
        </>}
        {err && <div className={err.includes("זמין בחבילת") ? "upsell" : "err"} role="alert">{err.includes("זמין בחבילת") ? "🔒 " : ""}{err}</div>}
      </div>
      {plan && <div className="card"><h3>תוכנית הסריקה</h3><p className="faint">{plan.cost}{plan.ready ? "" : " · אין מנוע חיפוש מוגדר"}</p><div className="sc-plan">{plan.plan.map((p: any, i: number) => <span key={i} className="tag" title={p.angle}>{p.query}{p.site ? " · " + p.site : ""}</span>)}</div></div>}
      {job && <Progress job={job} onCancel={cancel} />}
      {res && <Result r={res} />}
      {!res && !job && searches.length > 0 && <div className="faint sc-empty">עוד לא רצה סריקה. בחר עומק והפעל, והתוצאות יופיעו כאן עם ציון, התאמה לחיפוש וכפתורי יצירת קשר.</div>}
    </>}
    {view === "history" && <div className="card"><h3>סריקות אחרונות</h3>{hist.length === 0 && <p className="faint">עדיין אין היסטוריה.</p>}{hist.map(h => <div className="sc-h" key={h.id}><div><b>{h.search}</b><small className="faint">{h.at.replace("T", " ")} · {({ quick: "מהירה", standard: "רגילה", deep: "עמוקה", max: "מקסימלית" } as any)[h.depth]} · {h.seconds} ש׳</small></div>
      <span className="tag">{h.found} נמצאו</span><span className="tag good">{h.new} חדשות</span><div className="sc-top">{(h.top || []).map((t: any) => <a key={t.url} className={"sc-pill g" + t.grade} href={t.url} target="_blank" rel="noopener noreferrer nofollow" title={t.title}>{t.grade} · {t.title.slice(0, 28)}</a>)}</div></div>)}
      {res && <button className="ghost" onClick={() => setView("scan")}>חזרה לתוצאות האחרונות</button>}</div>}
    {view === "engines" && <div className="card"><h3>מנועי חיפוש</h3><p className="faint">הסריקות משתמשות במנועי חיפוש רשמיים בלבד. יותר מנועים ומפתחות הם יותר כיסוי ומכסה.</p><Engines api={api} isAdmin={isAdmin} /></div>}
  </div>;
}
