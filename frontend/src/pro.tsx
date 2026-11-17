import { useCallback, useEffect, useMemo, useState } from "react";
import { Icon } from "./listings";
import "./styles.pro.css";
type Api = (path: string, o?: any) => Promise<any>;

/** v3.13 Pro toolkit UI. Every tool talks to /api/pro/*; plan limits come from the server (402 with a Hebrew message). */
const fmt = (n: any) => (typeof n === "number" ? (Number.isInteger(n) ? n.toLocaleString("he-IL") : n.toLocaleString("he-IL", { maximumFractionDigits: 2 })) : String(n ?? ""));
const LBL: Record<string, string> = { monthly: "החזר חודשי", total_paid: "סה״כ ישולם", total_interest: "סה״כ ריבית", loan: "הלוואה", down_payment: "הון עצמי", ltv_pct: "מימון %", price: "מחיר", max_price: "מחיר מקסימלי", extra_total: "עלויות נלוות", extra_pct: "עלויות נלוות %",
  all_in: "עלות כוללת", cash_needed: "מזומן נדרש", gross_yield_pct: "תשואה ברוטו %", net_yield_pct: "תשואה נטו %", payback_years: "שנות החזר", annual_net: "נטו שנתי", invested: "סה״כ השקעה", monthly_cashflow: "תזרים חודשי", cash_on_cash_pct: "תשואה על ההון %",
  fair: "מחיר הוגן", low: "נמוך", high: "גבוה", pct_of_new: "% ממחיר חדש", total: "סה״כ", per_month: "לחודש", per_km: "לק״מ", resale_value: "שווי מכירה חוזרת", max_monthly_payment: "החזר מקסימלי", limited_by: "מוגבל על ידי", equity_used: "הון עצמי בשימוש",
  extra_costs: "עלויות נלוות", months: "חודשים", pti_pct: "החזר מההכנסה %", verdict: "הערכה", fair_low: "הוגן מ-", fair_mid: "הוגן (חציון)", fair_high: "הוגן עד", gap_pct: "פער מהחציון %", position: "מיקום", price_per_sqm: "מחיר למ״ר", market_sqm: "מ״ר בשוק", sqm_gap_pct: "פער מ״ר %", n: "מודעות דומות",
  open: "פתיחה", target: "יעד", walk_away: "סף יציאה", ask: "מבוקש", saving_at_target_pct: "חיסכון ביעד %", purchase_extra: "עלויות רכישה", median: "חציון", p25: "רבעון תחתון", p75: "רבעון עליון", min: "מינימום", max: "מקסימום", mean: "ממוצע" };
const HIDE = new Set(["note", "tip", "warnings", "schedule", "scenarios", "items", "breakdown", "enough", "enough_data", "kind", "lang", "levers", "tips", "message", "disclaimer", "price"]);
const HL = new Set(["monthly", "max_price", "all_in", "cash_needed", "fair", "net_yield_pct", "per_month", "open", "target", "fair_mid"]);

function View({ d }: { d: any }) {
  if (!d || typeof d !== "object") return null;
  const kv = Object.entries(d).filter(([k, v]) => !HIDE.has(k) && v !== null && v !== "" && (typeof v === "number" || typeof v === "string") && !(typeof v === "string" && v.length > 60));
  return <div className="pro-out">
    {kv.length > 0 && <div className="kvs">{kv.map(([k, v]) => <div key={k} className={"kv" + (HL.has(k) ? " hl" : "")}><small>{LBL[k] || k}</small><b>{fmt(v)}</b></div>)}</div>}
    {(d.warnings || []).map((w: string, i: number) => <div className="upsell" key={i}>⚠️ {w}</div>)}
    {d.items && <table><tbody>{d.items.map((i: any) => <tr key={i.name}><td>{i.name}</td><td>{fmt(i.amount)} ₪</td></tr>)}</tbody></table>}
    {d.breakdown && <table><tbody>{d.breakdown.map((i: any) => <tr key={i.name}><td>{i.name}</td><td>{fmt(i.amount)} ₪</td></tr>)}</tbody></table>}
    {d.scenarios && <div><small className="faint">תרחישי ריבית</small><div className="chips">{d.scenarios.map((s: any) => <span className="tag" key={s.rate_pct}>{s.rate_pct}% ← {fmt(s.monthly)} ₪</span>)}</div></div>}
    {d.schedule && <details><summary>לוח סילוקין שנתי</summary><table><thead><tr><th>שנה</th><th>קרן</th><th>ריבית</th><th>יתרה</th></tr></thead><tbody>{d.schedule.map((r: any) => <tr key={r.year}><td>{r.year}</td><td>{fmt(r.principal)}</td><td>{fmt(r.interest)}</td><td>{fmt(r.balance)}</td></tr>)}</tbody></table></details>}
    {d.note && <p className="faint">{d.note}</p>}{d.tip && <p className="faint">{d.tip}</p>}
  </div>;
}

function Upsell({ msg }: { msg: string }) { return msg ? <div className={msg.includes("זמין בחבילת") ? "upsell" : "err"} role="alert">{msg.includes("זמין בחבילת") ? "🔒 " : ""}{msg}</div> : null; }
function useRun(api: Api) {
  const [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const run = useCallback(async (fn: () => Promise<any>) => { try { setErr(""); setBusy(true); return await fn(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } }, []);
  return { err, busy, run, setErr };
}
const download = (name: string, mime: string, content: string) => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([content], { type: mime })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); };
const copy = (t: string) => navigator.clipboard?.writeText(t).catch(() => {});
const optLabel = (l: any) => `${l.score}% · ${l.title || l.extracted?.location || "הזדמנות"}${l.extracted?.price ? " · " + fmt(l.extracted.price) + " ₪" : ""}`;

/* ------------------------------------------------------------------ overview */
function Overview({ api, cat, go, isAdmin }: any) {
  const [adm, setAdm] = useState<any>(null);
  useEffect(() => { if (isAdmin) api("/api/admin/pro/overview").then(setAdm).catch(() => {}); }, [isAdmin]);
  if (!cat) return <div className="skel" style={{ blockSize: 120 }} />;
  const tabOf: Record<string, string> = { scan: "scan", analysis: "analyze", ai: "analyze", calc: "calc", crm: "crm", reports: "reports" };
  return <div className="pro">
    <div className="pro-hero"><h3>ארגז הכלים של Smart Sniper</h3><p>{cat.features.length} כלים: סריקה מורחבת, ניתוח הונאות ומו״מ, מחשבונים, מעקב לקוחות ודוחות ממותגים. החבילה שלך: <b>{({ starter: "Starter", pro: "Pro", vip: "VIP" } as any)[cat.plan]}</b>{cat.open_all && " (פתוח לכולם במצב בדיקה)"}.</p></div>
    {Object.entries(cat.groups).map(([g, name]: any) => <section key={g}><h4 style={{ margin: ".2rem 0 .6rem" }}>{name}</h4>
      <div className="pro-grid">{cat.features.filter((f: any) => f.group === g).map((f: any, i: number) => <div key={f.id} style={{ "--i": i } as any} className={"pro-card" + (f.allowed ? "" : " locked")}>
        <h4>{f.allowed ? <Icon n="check" /> : <span aria-hidden="true">🔒</span>}{f.name}</h4><p>{f.desc}</p>
        <div className="rowf"><span className={"pbadge " + f.plan}>{({ starter: "חינם", pro: "Pro", vip: "VIP" } as any)[f.plan]}</span>
          {f.reason === "trial" && <span className="trial">{f.trial_left} שימושי ניסיון החודש</span>}{!f.allowed && <span className="trial">שדרג כדי לפתוח</span>}
          <button className="ghost sm" style={{ marginInlineStart: "auto" }} onClick={() => go(tabOf[g])}>פתח</button></div></div>)}</div></section>)}
    {adm && <div className="pro-card"><h4>למנהל: מה נמכר החודש</h4><p>{adm.active_users} משתמשים פעילים · {adm.total_uses} שימושים</p>
      {adm.features.slice(0, 8).map((f: any) => <div className="rowf" key={f.id}><span style={{ minInlineSize: 150 }}>{f.name}</span><span className="meter"><i style={{ inlineSize: Math.min(100, (f.uses / Math.max(1, adm.features[0].uses)) * 100) + "%" }} /></span><b>{f.uses}</b></div>)}</div>}
  </div>;
}

/* ------------------------------------------------------------------ Scan+ */
function ScanPlus({ api, searches, onChanged }: any) {
  const [sid, setSid] = useState(""), [q, setQ] = useState(""), [n, setN] = useState(8), [plan, setPlan] = useState<any>(null), [res, setRes] = useState<any>(null), [rep, setRep] = useState<any>(null), [auto, setAuto] = useState<any>(null);
  const { err, busy, run } = useRun(api);
  useEffect(() => { if (!sid && searches[0]) setSid(searches[0].id); }, [searches]);
  useEffect(() => { api("/api/pro/scan/report").then(setRep).catch(() => {}); api("/api/pro/scan/auto").then(setAuto).catch(() => {}); }, []);
  const body = () => ({ search_id: sid, query: q || null, queries: n });
  return <div className="pro">
    <div className="pro-hero"><h3>סריקה מורחבת</h3><p>במקום שאילתה אחת לכל אתר, המערכת שואלת בכמה ניסוחים (כולל מחיר ואנגלית) ובכל אתרי המודעות, מדרגת את התוצאות, זורקת דפי אינדקס וכפילויות ומייבאת רק את הטובות. כל שאילתה צורכת חיפוש אחד ממכסת המנוע.</p></div>
    <div className="pro-form"><label>חיפוש<select value={sid} onChange={e => setSid(e.target.value)}>{searches.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>שאילתה חופשית (אופציונלי)<input value={q} maxLength={200} onChange={e => setQ(e.target.value)} placeholder="למשל: דירת 3 חדרים בחולון" /></label>
      <label>מספר שאילתות ({n})<input type="range" min={1} max={12} value={n} onChange={e => setN(+e.target.value)} /></label></div>
    <div className="rowf"><button className="ghost" disabled={busy || !sid} onClick={() => run(async () => setPlan(await api("/api/pro/scan/plus", { method: "POST", body: { ...body(), plan_only: true } })))}><Icon n="eye" /> תצוגה מקדימה (בלי עלות)</button>
      <button disabled={busy || !sid} onClick={() => run(async () => { setRes(await api("/api/pro/scan/plus", { method: "POST", body: body() })); onChanged && onChanged(); })}><Icon n="radar" /> {busy ? "סורק..." : "הפעל סריקה מורחבת"}</button></div>
    <Upsell msg={err} />{busy && <div className="skel" />}
    {plan && <div className="pro-out"><b>השאילתות שיישלחו</b><div className="chips">{plan.plan.map((p: any, i: number) => <span className="tag" key={i}>{p.query}{p.site ? " · " + p.site : ""}</span>)}</div><small className="faint">{plan.cost}</small></div>}
    {res && <div className="pro-out"><b>{res.summary.headline}</b>
      <div className="kvs">{[["נמצאו", res.found], ["נשארו אחרי סינון", res.kept], ["חדשות", res.new], ["נדחו", res.rejected], ["כפולות", res.duplicates]].map(([k, v]: any) => <div className="kv hl" key={k}><small>{k}</small><b>{v ?? 0}</b></div>)}</div>
      {res.top.map((t: any, i: number) => <div className="rowf" key={i}><span className="meter"><i style={{ inlineSize: t.rank + "%" }} /></span><a href={t.url} target="_blank" rel="noopener noreferrer nofollow" style={{ flex: 3, minInlineSize: 200 }}>{t.title}</a><span className="faint">{t.rank} · {(t.why || []).join(", ")}</span></div>)}
      <details><summary>דוח לכל שאילתה</summary><table><tbody>{res.report.map((r: any, i: number) => <tr key={i}><td>{r.query}{r.site ? " · " + r.site : ""}</td><td>{r.error ? "✗ " + r.error : r.found}</td></tr>)}</tbody></table></details></div>}
    {rep && <div className="pro-out"><b>בריאות מנועי חיפוש</b><div className="kvs"><div className="kv"><small>מנועים פעילים</small><b>{rep.configured.join(", ") || "אין"}</b></div><div className="kv"><small>שאילתות חינם בחודש (הערכה)</small><b>{fmt(rep.est_free_queries_per_month)}</b></div><div className="kv hl"><small>סריקות מורחבות בחודש</small><b>{fmt(rep.est_scans_per_month)}</b></div></div>
      {rep.advice.map((a: string, i: number) => <div className="sig" key={i}>💡 {a}</div>)}</div>}
    {auto && <AutoScan api={api} searches={searches} auto={auto} setAuto={setAuto} />}
  </div>;
}
function AutoScan({ api, searches, auto, setAuto }: any) {
  const { err, run } = useRun(api); const [f, setF] = useState({ enabled: auto.enabled, hours: auto.hours, search_ids: auto.search_ids || [], queries: auto.queries || 6 });
  const tog = (id: string) => setF({ ...f, search_ids: f.search_ids.includes(id) ? f.search_ids.filter((x: string) => x !== id) : [...f.search_ids, id].slice(0, 5) });
  return <div className="pro-out"><b>סריקה אוטומטית <span className="pbadge vip">VIP</span></b><p className="faint">החיפושים שתבחר נסרקים לבד כל כמה שעות. התוצאות מופיעות בהזדמנויות, והתראות לפי הכללים שלך.</p>
    <label className="rowf"><input type="checkbox" checked={f.enabled} onChange={e => setF({ ...f, enabled: e.target.checked })} style={{ inlineSize: "auto" }} /> פעיל</label>
    <div className="chips">{searches.map((s: any) => <button key={s.id} className="ghost sm" aria-pressed={f.search_ids.includes(s.id)} onClick={() => tog(s.id)} style={f.search_ids.includes(s.id) ? { borderColor: "var(--line-h)" } : {}}>{f.search_ids.includes(s.id) ? "✓ " : ""}{s.name}</button>)}</div>
    <div className="pro-form"><label>כל כמה שעות ({f.hours})<input type="range" min={6} max={168} step={6} value={f.hours} onChange={e => setF({ ...f, hours: +e.target.value })} /></label><label>שאילתות בסריקה ({f.queries})<input type="range" min={1} max={8} value={f.queries} onChange={e => setF({ ...f, queries: +e.target.value })} /></label></div>
    <button onClick={() => run(async () => setAuto(await api("/api/pro/scan/auto", { method: "PUT", body: f })))}>שמור</button><Upsell msg={err} />
    {(auto.log || []).slice().reverse().map((l: any, i: number) => <div className="faint" key={i}>{l.at.replace("T", " ")} · {l.search} · {l.error ? "שגיאה " + l.error : `${l.found} תוצאות, ${l.new} חדשות`}</div>)}</div>;
}

/* ------------------------------------------------------------------ Analyze a listing */
function Analyze({ api, listings, searches }: any) {
  const [lid, setLid] = useState(""), [out, setOut] = useState<any>({}), [lang, setLang] = useState("he"), [brand, setBrand] = useState<any>(null);
  const { err, busy, run } = useRun(api); const l = listings.find((x: any) => x.id === lid);
  useEffect(() => { if (!lid && listings[0]) setLid(listings[0].id); }, [listings]);
  const get = (k: string, path: string, o?: any) => run(async () => { const r = await api(`/api/pro/listings/${lid}/${path}`, o); setOut((p: any) => ({ ...p, [k]: r })); return r; });
  const all = async () => { for (const [k, p] of [["fraud", "fraud"], ["tags", "tags"], ["fair", "fair-price"], ["nego", `negotiation?lang=${lang}`], ["check", "checklist"]]) await get(k, p); };
  const tpl = (kind: string, tl: string) => run(async () => { const r = await api("/api/pro/templates", { method: "POST", body: { listing_id: lid, kind, lang: tl, tone: "friendly", offer: out.nego?.target || null } }); setOut((p: any) => ({ ...p, tpl: r })); });
  if (!listings.length) return <div className="pro-out">אין עדיין הזדמנויות לנתח. הבא מודעות בלשונית "חיפושים ומקורות" או בסריקה המורחבת.</div>;
  const fr = out.fraud;
  return <div className="pro">
    <div className="pro-form"><label>הזדמנות<select value={lid} onChange={e => { setLid(e.target.value); setOut({}); }}>{listings.map((x: any) => <option key={x.id} value={x.id}>{optLabel(x)}</option>)}</select></label>
      <label>שפה<select value={lang} onChange={e => setLang(e.target.value)}><option value="he">עברית</option><option value="en">English</option><option value="ru">Русский</option><option value="ar">العربية</option></select></label></div>
    <div className="rowf"><button disabled={busy || !lid} onClick={all}><Icon n="spark" /> הרץ ניתוח מלא</button>
      {[["fraud", "fraud", "shield", "הונאה"], ["fair", "fair-price", "target", "מחיר הוגן"], ["nego", `negotiation?lang=${lang}`, "chat", "משא ומתן"], ["tags", "tags", "layers", "תגיות"], ["check", "checklist", "check", "רשימת בדיקה"], ["share", "share-pack", "send", "שיתוף"]].map(([k, p, ic, t]) =>
        <button key={k} className="ghost sm" disabled={busy || !lid} onClick={() => get(k, p)}><Icon n={ic} />{t}</button>)}
      <button className="ghost sm" disabled={busy || !lid} onClick={() => run(async () => { const r = await api(`/api/pro/listings/${lid}/sheet`); window.open(URL.createObjectURL(new Blob([r.content], { type: "text/html" })), "_blank"); })}><Icon n="download" />דף עסקה</button>
      <button className="ghost sm" disabled={busy || !lid} onClick={() => get("ai", "ai", { method: "POST", body: { action: "analyze" } })}><Icon n="bot" />אנליסט AI</button>
      <button className="ghost sm" disabled={busy || !lid} onClick={() => get("tr", "ai", { method: "POST", body: { action: "translate", lang: lang === "he" ? "en" : lang } })}>תרגום</button></div>
    <Upsell msg={err} />{busy && <div className="skel" />}
    {fr && <div className="pro-out"><div className="rowf"><div className={"gauge " + (fr.level === "high" ? "high" : fr.level === "medium" ? "med" : "")} style={{ "--p": fr.risk } as any}><b>{fr.risk}</b></div><div><b>סיכון הונאה: {fr.level_he}</b><p className="faint">{fr.disclaimer}</p></div></div>
      {fr.signals.map((s: any) => <div className="sig" key={s.code}><b>+{s.weight}</b>{s.why}</div>)}{fr.advice.map((a: string, i: number) => <div className="sig" key={i}>🛡️ {a}</div>)}</div>}
    {out.fair && <View d={out.fair} />}
    {out.nego && (out.nego.enough ? <div className="pro-out"><View d={out.nego} />{out.nego.levers.map((x: string, i: number) => <div className="sig" key={i}>⚡ {x}</div>)}<pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{out.nego.message}</pre><button className="ghost sm" onClick={() => copy(out.nego.message)}><Icon n="copy" />העתק</button></div> : <div className="pro-out">{out.nego.note}</div>)}
    {out.tags && <div className="pro-out"><div className="chips">{out.tags.tags.map((t: any) => <span className="tag good" key={t.code}>{t.label}</span>)}</div></div>}
    {out.check && <div className="pro-out">{out.check.groups.map((g: any) => <div key={g.title}><b>{g.title}</b><ul>{g.items.map((i: string) => <li key={i}>{i}</li>)}</ul></div>)}</div>}
    {out.ai && <div className="pro-out"><b>{out.ai.engine === "ai" ? "ניתוח AI" : "ניתוח לפי כללים"}</b><p>{out.ai.summary}</p>{[["יתרונות", "pros", "✅"], ["חסרונות", "cons", "⚠️"], ["שאלות למוכר", "questions", "❓"]].map(([t, k, e]: any) => out.ai[k]?.length > 0 && <div key={k}><b>{t}</b>{out.ai[k].map((x: string, i: number) => <div className="sig" key={i}>{e} {x}</div>)}</div>)}</div>}
    {out.tr && <div className="pro-out"><b>{out.tr.engine === "ai" ? "תרגום" : "מקור"}</b><p style={{ whiteSpace: "pre-wrap" }}>{out.tr.text}</p>{out.tr.note && <small className="faint">{out.tr.note}</small>}</div>}
    {out.share && <div className="pro-out"><b>חבילת שיתוף</b><pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{out.share.whatsapp}</pre>
      <div className="rowf"><button className="ghost sm" onClick={() => copy(out.share.whatsapp)}><Icon n="copy" />העתק</button><a className="btn wa sm" target="_blank" rel="noopener noreferrer" href={"https://wa.me/?text=" + encodeURIComponent(out.share.whatsapp)}><Icon n="chat" />וואטסאפ</a><a className="btn src sm" href={`mailto:?subject=${encodeURIComponent(out.share.email.subject)}&body=${encodeURIComponent(out.share.email.body)}`}><Icon n="mail" />מייל</a></div></div>}
    <div className="pro-out"><b>הודעות מוכנות לבעל המודעה</b><div className="rowf">{[["first", "פנייה"], ["followup", "מעקב"], ["offer", "הצעה"], ["visit", "צפייה"], ["thanks", "תודה"]].map(([k, t]) => <button key={k} className="ghost sm" disabled={busy || !lid} onClick={() => tpl(k, lang)}>{t}</button>)}</div>
      {out.tpl && <><pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{out.tpl.text}</pre><button className="ghost sm" onClick={() => copy(out.tpl.text)}><Icon n="copy" />העתק</button></>}
      <small className="faint">שום דבר לא נשלח אוטומטית. אתה מעתיק ושולח בעצמך.</small></div>
    {lid && <CrmMini api={api} lid={lid} />}
  </div>;
}

function CrmMini({ api, lid }: any) {
  const [e, setE] = useState<any>(null), [note, setNote] = useState(""), [due, setDue] = useState(""); const { err, run } = useRun(api);
  const ST: [string, string][] = [["new", "חדש"], ["contacted", "נוצר קשר"], ["viewing", "צפייה"], ["negotiating", "משא ומתן"], ["won", "נסגר"], ["lost", "לא רלוונטי"]];
  useEffect(() => { api(`/api/pro/crm/${lid}`).then(setE).catch(() => setE(null)); }, [lid]);
  const save = (b: any) => run(async () => { setE(await api(`/api/pro/crm/${lid}`, { method: "PUT", body: b })); setNote(""); });
  return <div className="pro-out"><b>מעקב על ההזדמנות</b><div className="chips">{ST.map(([k, t]) => <button key={k} className="ghost sm" aria-pressed={e?.stage === k} style={e?.stage === k ? { borderColor: "var(--line-h)", background: "var(--sig-soft)" } : {}} onClick={() => save({ stage: k })}>{t}</button>)}</div>
    <div className="pro-form"><label>הערה<input value={note} maxLength={500} onChange={x => setNote(x.target.value)} placeholder="מה דובר?" /></label><label>תזכורת<input type="date" value={due} onChange={x => setDue(x.target.value)} /></label>
      <button disabled={!note && !due} onClick={() => save({ ...(note ? { note } : {}), ...(due ? { due } : {}) })}>שמור</button></div>
    <Upsell msg={err} />{e?.due && <small className="faint">תזכורת: {e.due}</small>}{(e?.notes || []).map((n: any, i: number) => <div className="sig" key={i}><small className="faint">{n.t.slice(0, 10)}</small>{n.text}</div>)}</div>;
}

/* ------------------------------------------------------------------ Compare + duplicates */
function Compare({ api, listings }: any) {
  const [sel, setSel] = useState<string[]>([]), [w, setW] = useState<any>({ score: 30, price: 25, sqm: 15, rooms: 10, risk: 15, extras: 5 }), [res, setRes] = useState<any>(null), [cl, setCl] = useState<any>(null); const { err, busy, run } = useRun(api);
  const names: any = { score: "ציון", price: "מחיר", sqm: "מחיר למ״ר", rooms: "חדרים", risk: "סיכונים", extras: "מאפיינים" };
  const by = useMemo(() => Object.fromEntries(listings.map((l: any) => [l.id, l])), [listings]);
  return <div className="pro"><div className="pro-hero"><h3>השוואה ואיחוד כפילויות</h3><p>בחר 2-6 הזדמנויות, קבע מה חשוב לך, וקבל מנצח עם הסבר.</p></div>
    <div className="chips">{listings.slice(0, 40).map((l: any) => <button key={l.id} className="ghost sm" onClick={() => setSel(sel.includes(l.id) ? sel.filter(x => x !== l.id) : [...sel, l.id].slice(0, 6))} style={sel.includes(l.id) ? { borderColor: "var(--line-h)", background: "var(--sig-soft)" } : {}}>{sel.includes(l.id) ? "✓ " : ""}{optLabel(l)}</button>)}</div>
    <div className="pro-form">{Object.keys(w).map(k => <label key={k}>{names[k]} ({w[k]})<input type="range" min={0} max={100} value={w[k]} onChange={e => setW({ ...w, [k]: +e.target.value })} /></label>)}</div>
    <div className="rowf"><button disabled={busy || sel.length < 2} onClick={() => run(async () => setRes(await api("/api/pro/compare", { method: "POST", body: { ids: sel, weights: w } })))}><Icon n="layers" /> השווה ({sel.length})</button>
      <button className="ghost" disabled={busy} onClick={() => run(async () => setCl(await api("/api/pro/clusters")))}>מצא כפילויות</button></div><Upsell msg={err} />
    {res && <div className="pro-out">{res.ranking.map((r: any, i: number) => <div className="rowf" key={r.id}><b style={{ minInlineSize: 22 }}>{i + 1}</b><span style={{ flex: 2, minInlineSize: 160 }}>{r.title} {i === 0 && "🏆"}</span><span className="meter"><i style={{ inlineSize: r.total + "%" }} /></span><b>{r.total}</b><small className="faint" style={{ flexBasis: "100%" }}>{r.why}{r.price ? ` · ${fmt(r.price)} ₪` : ""}</small></div>)}</div>}
    {cl && <div className="pro-out"><b>{cl.groups.length ? `${cl.groups.length} קבוצות של אותו נכס (נסרקו ${cl.scanned})` : `לא נמצאו כפילויות (נסרקו ${cl.scanned})`}</b>
      {cl.groups.map((g: any, i: number) => <div className="lead" key={i}>{g.count} מודעות · הפרש מחיר {fmt(g.price_spread)} ₪{g.items.map((it: any) => <div key={it.id} className="rowf"><span>{it.score}% · {it.location || ""} {it.price ? fmt(it.price) + " ₪" : ""}</span>{it.id === g.cheapest && <span className="tag good">הזול</span>}{it.url && <a href={it.url} target="_blank" rel="noopener noreferrer nofollow">מקור</a>}{by[it.id] && <span className="faint">{by[it.id].title}</span>}</div>)}</div>)}</div>}
  </div>;
}

/* ------------------------------------------------------------------ Calculators */
const KINDS: [string, string][] = [["first", "דירה ראשונה"], ["upgrade", "משפר דיור"], ["investment", "השקעה"]];
const CALCS: any[] = [
  { id: "mortgage", t: "משכנתא", path: "mortgage", f: [["price", "מחיר הנכס", 2000000], ["ltv_pct", "אחוז מימון", 70], ["rate_pct", "ריבית שנתית %", 4.5], ["years", "שנים", 25], ["income_monthly", "הכנסה חודשית (לבדיקת החזר)", ""], ["kind", "סוג", "first", KINDS]] },
  { id: "afford", t: "כוח קנייה", path: "affordability", f: [["income_monthly", "הכנסה חודשית נטו", 25000], ["savings", "חיסכון והון עצמי", 600000], ["loans_monthly", "החזרי הלוואות קיימים", 0], ["rate_pct", "ריבית %", 4.5], ["years", "שנים", 25], ["kind", "סוג", "first", KINDS]] },
  { id: "costs", t: "עלויות ומס רכישה", path: "purchase-costs", f: [["price", "מחיר", 2500000], ["kind", "סוג דירה", "single", [["single", "דירה יחידה"], ["additional", "דירה נוספת"]]], ["broker", "תיווך", "false", [["false", "ללא"], ["true", "עם תיווך"]]], ["renovation", "שיפוץ", 0], ["down_payment", "הון עצמי (לחישוב מזומן)", ""]] },
  { id: "yield", t: "תשואה", path: "yield", f: [["price", "מחיר הנכס", 2000000], ["monthly_rent", "שכירות חודשית", 6000], ["annual_costs", "עלויות שנתיות", 6000], ["vacancy_pct", "אי-תפוסה %", 4], ["loan", "הלוואה (אופציונלי)", ""], ["rate_pct", "ריבית %", 4.5]] },
  { id: "vehicle", t: "עלות רכב", path: "vehicle", f: [["price", "מחיר הרכב", 120000], ["years", "שנות החזקה", 4], ["km_year", "ק״מ בשנה", 15000], ["l_per_100", "ליטר ל-100 ק״מ", 7.5], ["fuel_price", "מחיר ליטר", 7.5], ["insurance_year", "ביטוח בשנה", 4500], ["maintenance_year", "טיפולים בשנה", 3000]] },
  { id: "used", t: "מחיר יד שנייה", path: "used-price", f: [["new_price", "מחיר חדש", 5000], ["age_months", "גיל בחודשים", 18], ["condition", "מצב", "good", [["like_new", "כמו חדש"], ["good", "טוב"], ["fair", "סביר"], ["poor", "גרוע"]]], ["category", "סוג", "phone", [["phone", "טלפון"], ["laptop", "מחשב"], ["tv", "טלוויזיה"], ["appliance", "מכשיר חשמלי"], ["furniture", "ריהוט"], ["console", "קונסולה"], ["other", "אחר"]]]] },
];
function Calc({ api }: any) {
  const [cid, setCid] = useState("mortgage"), [vals, setVals] = useState<any>({}), [out, setOut] = useState<any>(null); const { err, busy, run } = useRun(api); const c = CALCS.find(x => x.id === cid);
  const val = (k: string, d: any) => vals[cid + k] ?? d;
  const go = () => run(async () => { const b: any = {}; for (const [k, , d] of c.f) { const v = val(k, d); if (v === "" || v === null) continue; b[k] = k === "broker" ? v === "true" : (typeof d === "number" ? Number(v) : v); } setOut(await api("/api/pro/calc/" + c.path, { method: "POST", body: b })); });
  return <div className="pro"><div className="seg" role="tablist">{CALCS.map(x => <button key={x.id} aria-pressed={cid === x.id} onClick={() => { setCid(x.id); setOut(null); }}>{x.t}</button>)}</div>
    <div className="pro-form">{c.f.map(([k, l, d, opts]: any) => <label key={k}>{l}{opts ? <select value={val(k, d)} onChange={e => setVals({ ...vals, [cid + k]: e.target.value })}>{opts.map(([v, t]: any) => <option key={v} value={v}>{t}</option>)}</select> : <input inputMode="decimal" value={val(k, d)} onChange={e => setVals({ ...vals, [cid + k]: e.target.value.replace(/[^\d.]/g, "") })} />}</label>)}
      <button disabled={busy} onClick={go}>חשב</button></div><Upsell msg={err} />{out && <View d={out} />}
    <small className="faint">הערכות בלבד, לא ייעוץ פיננסי או משפטי. מדרגות מס הרכישה מעודכנות ל-2026 ונבדקות מול רשות המסים.</small></div>;
}

/* ------------------------------------------------------------------ CRM + clients */
function Crm({ api }: any) {
  const [board, setBoard] = useState<any>(null), [rem, setRem] = useState<any[]>([]), [clients, setClients] = useState<any[]>([]), [cf, setCf] = useState<any>({ name: "", budget_max: "", cities: "", rooms_min: "", must: "" }), [m, setM] = useState<any>(null); const { err, run } = useRun(api);
  const load = useCallback(() => { run(async () => { setBoard(await api("/api/pro/crm")); setRem((await api("/api/pro/reminders")).items); }); api("/api/pro/clients").then((r: any) => setClients(r.clients)).catch(() => {}); }, []);
  useEffect(() => { load(); }, []);
  const addClient = () => run(async () => { const c = { ...cf, budget_max: cf.budget_max ? +cf.budget_max : null, rooms_min: cf.rooms_min ? +cf.rooms_min : null, cities: cf.cities.split(",").map((x: string) => x.trim()).filter(Boolean), must: cf.must.split(",").map((x: string) => x.trim()).filter(Boolean) }; setClients((await api("/api/pro/clients", { method: "PUT", body: { clients: [...clients, c] } })).clients); setCf({ name: "", budget_max: "", cities: "", rooms_min: "", must: "" }); });
  return <div className="pro"><Upsell msg={err} />
    {rem.length > 0 && <div className="pro-out"><b>תזכורות ({rem.length})</b>{rem.map(r => <div key={r.listing_id} className={"lead" + (r.overdue ? " over" : "")}>{r.overdue ? "⏰ באיחור " : r.today ? "📅 היום " : "🗓️ "}{r.due} · {r.title || r.listing_id.slice(0, 6)} {r.last_note && <span className="faint">· {r.last_note}</span>}</div>)}</div>}
    {board && <div className="board">{board.stages.map((s: any) => <div className="col" key={s.id}><h5><span>{s.label}</span><span>{s.items.length}</span></h5>{s.items.map((i: any) => <div className="lead" key={i.id}><b>{i.score}%</b> {i.title}{i.price ? ` · ${fmt(i.price)} ₪` : ""}{i.due && <div className="faint">תזכורת {i.due}</div>}{i.last_note && <div className="faint">{i.last_note}</div>}</div>)}</div>)}</div>}
    {board && board.tracked === 0 && <div className="pro-out">עוד אין הזדמנויות במעקב. פתח הזדמנות בלשונית "ניתוח" וסמן שלב.</div>}
    <div className="pro-out"><b>לקוחות (למתווכים) <span className="pbadge vip">VIP</span></b><div className="pro-form"><label>שם<input value={cf.name} onChange={e => setCf({ ...cf, name: e.target.value })} /></label><label>תקציב מקסימלי<input inputMode="numeric" value={cf.budget_max} onChange={e => setCf({ ...cf, budget_max: e.target.value.replace(/\D/g, "") })} /></label>
      <label>ערים (בפסיק)<input value={cf.cities} onChange={e => setCf({ ...cf, cities: e.target.value })} placeholder="Holon, Bat Yam" /></label><label>חדרים מינימום<input inputMode="decimal" value={cf.rooms_min} onChange={e => setCf({ ...cf, rooms_min: e.target.value })} /></label>
      <label>חייב להיות (בפסיק)<input value={cf.must} onChange={e => setCf({ ...cf, must: e.target.value })} placeholder="חניה, מעלית" /></label><button disabled={!cf.name} onClick={addClient}>הוסף לקוח</button></div>
      {clients.map(c => <div className="rowf" key={c.id}><b>{c.name}</b><span className="faint">{c.budget_max ? fmt(c.budget_max) + " ₪" : ""} {(c.cities || []).join(", ")}</span>
        <button className="ghost sm" style={{ marginInlineStart: "auto" }} onClick={() => run(async () => setM(await api(`/api/pro/clients/${c.id}/matches`)))}>מצא התאמות</button><button className="ghost sm danger" onClick={() => run(async () => setClients((await api("/api/pro/clients", { method: "PUT", body: { clients: clients.filter(x => x.id !== c.id) } })).clients))}>מחק</button></div>)}
      {m && <div><b>התאמות עבור {m.client.name}</b>{m.matches.length === 0 && <div className="faint">אין עדיין התאמות מעל 50%.</div>}{m.matches.map((x: any) => <div className="lead" key={x.id}><div className="rowf"><span className="meter"><i style={{ inlineSize: x.fit + "%" }} /></span><b>{x.fit}%</b><span>{x.title}{x.price ? ` · ${fmt(x.price)} ₪` : ""}</span></div><small className="faint">{x.reasons.join(" · ")}{x.blockers.length ? " | " + x.blockers.join(", ") : ""}</small><div><button className="ghost sm" onClick={() => copy(x.message)}><Icon n="copy" />העתק הודעה ללקוח</button></div></div>)}</div>}</div></div>;
}

/* ------------------------------------------------------------------ Alert rules */
function Rules({ api }: any) {
  const [rules, setRules] = useState<any[]>([]), [limit, setLimit] = useState(2), [f, setF] = useState<any>({ name: "", city: "", max_price: "", rooms_min: "", min_score: 70, keywords: "" }), [test, setTest] = useState<any>(null); const { err, run } = useRun(api);
  useEffect(() => { api("/api/pro/rules").then((r: any) => { setRules(r.rules); setLimit(r.limit); }).catch(() => {}); }, []);
  const rule = () => ({ name: f.name || "כלל", city: f.city || null, max_price: f.max_price ? +f.max_price : null, rooms_min: f.rooms_min ? +f.rooms_min : null, min_score: +f.min_score || 0, keywords: f.keywords.split(",").map((x: string) => x.trim()).filter(Boolean) });
  const save = (rs: any[]) => run(async () => setRules((await api("/api/pro/rules", { method: "PUT", body: { rules: rs } })).rules));
  return <div className="pro"><div className="pro-hero"><h3>כללי התראה</h3><p>הגדר מה נחשב הזדמנות בשבילך, ונשלח התראה באפליקציה כשהזדמנות חדשה מתאימה (נבדק כל כמה דקות). עד {limit} כללים בחבילה שלך.</p></div>
    <div className="pro-form"><label>שם<input value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></label><label>עיר<input value={f.city} onChange={e => setF({ ...f, city: e.target.value })} /></label><label>מחיר מקסימלי<input inputMode="numeric" value={f.max_price} onChange={e => setF({ ...f, max_price: e.target.value.replace(/\D/g, "") })} /></label>
      <label>חדרים מינימום<input inputMode="decimal" value={f.rooms_min} onChange={e => setF({ ...f, rooms_min: e.target.value })} /></label><label>ציון מינימלי ({f.min_score})<input type="range" min={0} max={100} value={f.min_score} onChange={e => setF({ ...f, min_score: +e.target.value })} /></label><label>מילים חובה (בפסיק)<input value={f.keywords} onChange={e => setF({ ...f, keywords: e.target.value })} /></label></div>
    <div className="rowf"><button className="ghost" onClick={() => run(async () => setTest(await api("/api/pro/rules/test", { method: "POST", body: { rule: rule() } })))}>בדוק על הקיים</button><button disabled={rules.length >= limit} onClick={() => save([...rules, rule()])}>הוסף כלל</button></div><Upsell msg={err} />
    {test && <div className="pro-out"><b>{test.matches} התאמות מהאחרונות</b>{test.sample.map((s: any) => <div className="sig" key={s.id}>{s.score}% · {s.title}{s.price ? ` · ${fmt(s.price)} ₪` : ""}</div>)}</div>}
    {rules.map((r, i) => <div className="pro-card" key={r.id} style={{ "--i": i } as any}><div className="rowf"><h4>{r.name}</h4><span className="faint">{[r.city, r.max_price && "עד " + fmt(r.max_price), r.rooms_min && r.rooms_min + "+ חד׳", r.min_score && r.min_score + "%+", ...(r.keywords || [])].filter(Boolean).join(" · ")}</span>
      <button className="ghost sm" style={{ marginInlineStart: "auto" }} onClick={() => save(rules.map(x => x.id === r.id ? { ...x, active: !x.active } : x))}>{r.active ? "פעיל" : "מושהה"}</button><button className="ghost sm danger" onClick={() => save(rules.filter(x => x.id !== r.id))}>מחק</button></div></div>)}</div>;
}

/* ------------------------------------------------------------------ Reports, export, brand, smart paste */
function Reports({ api, searches, onChanged }: any) {
  const [cat, setCat] = useState("real_estate"), [loc, setLoc] = useState(""), [rep, setRep] = useState<any>(null), [wk, setWk] = useState<any>(null), [brand, setBrand] = useState<any>({ name: "", phone: "", email: "", tagline: "", color: "#1f6feb" }), [paste, setPaste] = useState(""), [pr, setPr] = useState<any>(null), [sid, setSid] = useState(""), [msg, setMsg] = useState(""); const { err, busy, run } = useRun(api);
  useEffect(() => { api("/api/pro/settings").then((r: any) => r.brand && setBrand(r.brand)).catch(() => {}); }, []);
  useEffect(() => { if (!sid && searches[0]) setSid(searches[0].id); }, [searches]);
  return <div className="pro"><Upsell msg={err} />{msg && <div className="pro-out">{msg}</div>}
    <div className="pro-out"><b>דוח שוק</b><div className="pro-form"><label>קטגוריה<select value={cat} onChange={e => setCat(e.target.value)}><option value="real_estate">נדל״ן</option><option value="vehicles">רכב</option><option value="electronics">אלקטרוניקה</option><option value="furniture">ריהוט</option></select></label><label>עיר (אופציונלי)<input value={loc} onChange={e => setLoc(e.target.value)} placeholder="Holon" /></label>
      <button disabled={busy} onClick={() => run(async () => setRep(await api(`/api/pro/report/market?category=${cat}${loc ? "&location=" + encodeURIComponent(loc) : ""}`)))}>הפק דוח</button></div>
      {rep && <><View d={rep.overall} />{rep.sqm && <View d={{ "חציון למ״ר": rep.sqm.median, "מינימום למ״ר": rep.sqm.min, "מקסימום למ״ר": rep.sqm.max }} />}{rep.trend_he && <div className="sig">📈 מגמה: {rep.trend_he} ({rep.trend_pct}%)</div>}
        {rep.by_rooms.length > 0 && <table><thead><tr><th>חדרים</th><th>מודעות</th><th>חציון</th></tr></thead><tbody>{rep.by_rooms.map((r: any) => <tr key={r.key}><td>{r.key}</td><td>{r.n}</td><td>{fmt(r.median)} ₪</td></tr>)}</tbody></table>}
        {rep.cheapest.map((c: any) => <div className="sig" key={c.id}><b>-{c.below_median_pct}%</b>{c.location} {c.rooms ? c.rooms + " חד׳" : ""} · {fmt(c.price)} ₪</div>)}{rep.n === 0 && <div className="faint">אין עדיין נתונים בקטגוריה הזו.</div>}</>}</div>
    <div className="pro-out"><b>תקציר שבועי</b><div className="rowf"><button disabled={busy} onClick={() => run(async () => setWk(await api("/api/pro/report/weekly")))}>הפק</button><button className="ghost" disabled={busy} onClick={() => run(async () => { await api("/api/pro/report/weekly/send", { method: "POST" }); setMsg("נשלח למייל שלך"); })}><Icon n="mail" />שלח אליי</button>
      <button className="ghost" disabled={busy} onClick={() => run(async () => { const r = await api("/api/pro/export/csv"); download(r.filename, r.mime, r.content); setMsg(`יוצאו ${r.rows} הזדמנויות`); })}><Icon n="download" />ייצוא CSV</button></div>
      {wk && <><b>{wk.subject}</b><pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{wk.body}</pre><button className="ghost sm" onClick={() => copy(wk.subject + "\n\n" + wk.body)}><Icon n="copy" />העתק</button></>}</div>
    <div className="pro-out"><b>הדבקה חכמה (וואטסאפ / פייסבוק)</b><p className="faint">הדבק שיחה או רשימת מודעות. המערכת מנקה אימוג׳ים, שמות וחותמות זמן, ומפצלת למודעות נפרדות.</p>
      <textarea rows={4} value={paste} onChange={e => setPaste(e.target.value)} placeholder="[16/11/2026, 10:01] דנה: דירת 3 חדרים בחולון..." />
      <div className="rowf"><select value={sid} onChange={e => setSid(e.target.value)} style={{ inlineSize: "auto" }}>{searches.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><button className="ghost" disabled={busy || paste.length < 15} onClick={() => run(async () => setPr(await api("/api/pro/paste/clean", { method: "POST", body: { text: paste } })))}>נקה ופצל</button>
        <button disabled={busy || paste.length < 15 || !sid} onClick={() => run(async () => { setPr(await api("/api/pro/paste/clean", { method: "POST", body: { text: paste, search_id: sid } })); onChanged && onChanged(); })}>נקה ויבא</button></div>
      {pr && <div><b>נמצאו {pr.found} מודעות ({pr.source === "whatsapp" ? "שיחת וואטסאפ" : "טקסט רגיל"})</b>{pr.import && <div className="sig">יובאו: {pr.import.new} חדשות · {pr.import.rejected} נדחו · {pr.import.duplicates} כפולות</div>}{pr.parts.slice(0, 5).map((p: string, i: number) => <div className="lead" key={i} style={{ whiteSpace: "pre-wrap" }}>{p.slice(0, 220)}</div>)}</div>}</div>
    <div className="pro-out"><b>מיתוג עסקי <span className="pbadge vip">VIP</span></b><p className="faint">השם והצבע מופיעים בדף העסקה, בחבילת השיתוף ובתקציר.</p>
      <div className="pro-form">{[["name", "שם העסק"], ["phone", "טלפון"], ["email", "מייל"], ["tagline", "סלוגן"]].map(([k, l]) => <label key={k}>{l}<input value={brand[k] || ""} onChange={e => setBrand({ ...brand, [k]: e.target.value })} /></label>)}<label>צבע<input type="color" value={brand.color || "#1f6feb"} onChange={e => setBrand({ ...brand, color: e.target.value })} /></label>
        <button disabled={busy} onClick={() => run(async () => { setBrand((await api("/api/pro/settings", { method: "PUT", body: brand })).brand); setMsg("המיתוג נשמר"); })}>שמור מיתוג</button></div></div>
  </div>;
}

/* ------------------------------------------------------------------ shell */
const SUB: [string, string, string][] = [["overview", "סקירה", "layers"], ["scan", "סריקה+", "radar"], ["analyze", "ניתוח", "target"], ["compare", "השוואה", "star"], ["calc", "מחשבונים", "bolt"], ["crm", "מעקב ולקוחות", "user"], ["alerts", "התראות", "bell"], ["reports", "דוחות ומיתוג", "download"]];
export function ProPanel({ api, listings = [], searches = [], isAdmin = false, onChanged }: { api: Api; listings?: any[]; searches?: any[]; isAdmin?: boolean; onChanged?: () => void }) {
  const [sub, setSub] = useState("overview"), [cat, setCat] = useState<any>(null);
  const loadCat = useCallback(() => api("/api/pro/catalog").then(setCat).catch(() => {}), []);
  useEffect(() => { loadCat(); }, [sub]);
  return <div className="pro"><div className="seg" role="tablist" aria-label="כלי פרו">{SUB.map(([k, t, ic]) => <button key={k} role="tab" aria-pressed={sub === k} onClick={() => setSub(k)}><Icon n={ic} />{t}</button>)}</div>
    {sub === "overview" && <Overview api={api} cat={cat} isAdmin={isAdmin} go={(t: string) => setSub(t)} />}
    {sub === "scan" && <ScanPlus api={api} searches={searches} onChanged={onChanged} />}
    {sub === "analyze" && <Analyze api={api} listings={listings} searches={searches} />}
    {sub === "compare" && <Compare api={api} listings={listings} />}
    {sub === "calc" && <Calc api={api} />}
    {sub === "crm" && <Crm api={api} />}
    {sub === "alerts" && <Rules api={api} />}
    {sub === "reports" && <Reports api={api} searches={searches} onChanged={onChanged} />}
  </div>;
}
export { ScanPlus };
