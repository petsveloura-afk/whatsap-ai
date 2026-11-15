import { useEffect, useState, useCallback } from "react";
import { CATEGORIES, toSearchBody, isHttpsUrl, fmtPrice } from "./lib/search";

type Api = (path: string, o?: any) => Promise<any>;

/** Natural-language search wizard: /api/searches/parse -> editable preview -> /api/searches */
export function Wizard({ api, onCreated }: { api: Api; onCreated: () => void }) {
  const [text, setText] = useState(""), [res, setRes] = useState<any>(null), [cat, setCat] = useState(""), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false);
  const parse = async () => { try { setMsg(""); setBusy(true); const r = await api("/api/searches/parse", { method: "POST", body: { text } }); setRes(r); setCat(r.params.category || ""); } catch (e: any) { setMsg(e.message); } finally { setBusy(false); } };
  const create = async () => {
    try { setMsg(""); await api("/api/searches", { method: "POST", body: toSearchBody(res.params, cat) }); setMsg("החיפוש נוצר"); setRes(null); setText(""); onCreated(); } catch (e: any) { setMsg(e.message); }
  };
  const p = res?.params;
  return <div className="card"><h3>אשף חיפוש בשפה טבעית</h3>
    <textarea rows={2} style={{ width: "100%" }} value={text} onChange={e => setText(e.target.value)} placeholder="דירת 3 חדרים משופצת בחולון או בבת ים, עד 5,500 ש״ח, ללא תיווך" />
    <button onClick={parse} disabled={busy || text.length < 5}>נתח את הבקשה</button>
    {p && <div>
      {res.clarifications.map((q: string) => <div className="risk" key={q}>❓ {q}</div>)}
      <div>שם: {p.name} · מיקום: {p.locations.join(", ") || "?"} · תקציב מקסימלי: {fmtPrice(p.max_price)} · מילות הדרה: {p.excluded_keywords.join(", ") || "-"}</div>
      {!p.category && <select value={cat} onChange={e => setCat(e.target.value)}><option value="">בחר סוג</option>{Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}
      <button onClick={create} disabled={!p.category && !cat}>צור חיפוש</button>
    </div>}
    <div className="err">{msg}</div></div>;
}

/** Scout sources: RSS / JSON Feed URLs you are allowed to read. Polling runs in the server worker. */
export function SourcesPanel({ api, searches }: { api: Api; searches: any[] }) {
  const [src, setSrc] = useState<any[]>([]), [f, setF] = useState({ search_id: "", kind: "rss", url: "" }), [ev, setEv] = useState<any[]>([]), [msg, setMsg] = useState("");
  const load = useCallback(async () => { try { setSrc(await api("/api/sources")); } catch (e: any) { setMsg(e.message); } }, []);
  useEffect(() => { load(); }, []);
  const act = async (fn: () => Promise<any>) => { try { setMsg(""); await fn(); await load(); } catch (e: any) { setMsg(e.message); } };
  return <div className="card"><h3>מקורות (Scout)</h3>
    <div>מקורות מורשים בלבד: RSS/Atom או JSON Feed ציבוריים. המערכת מכבדת robots.txt וחוסמת כתובות פנימיות.</div>
    <select value={f.search_id} onChange={e => setF({ ...f, search_id: e.target.value })}><option value="">חיפוש</option>{searches.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
    <select value={f.kind} onChange={e => setF({ ...f, kind: e.target.value })}><option value="rss">RSS/Atom</option><option value="jsonfeed">JSON Feed</option></select>
    <input placeholder="https://..." value={f.url} onChange={e => setF({ ...f, url: e.target.value })} />
    <button disabled={!f.search_id || !isHttpsUrl(f.url)} onClick={() => act(async () => { await api("/api/sources", { method: "POST", body: f }); setF({ ...f, url: "" }); })}>הוסף</button>
    <table><tbody>{src.map(s => <tr key={s.id}><td>{s.url}</td><td className={s.status === "ERROR" ? "err" : "ok"}>{s.status}</td><td>{s.last_error || ""}</td>
      <td><button className="ghost" onClick={() => act(async () => { const r = await api(`/api/sources/${s.id}/poll`, { method: "POST" }); setMsg(r.queued ? "נוסף לתור" : r.note); })}>בדוק עכשיו</button>
        <button className="ghost" onClick={async () => setEv(await api(`/api/sources/${s.id}/events`))}>אירועים</button>
        <button className="ghost" onClick={() => act(() => api(`/api/sources/${s.id}`, { method: "DELETE" }))}>מחק</button></td></tr>)}</tbody></table>
    {ev.map((e, i) => <div key={i}>{e.at} · {e.status} · {e.detail}</div>)}
    <div className="err">{msg}</div></div>;
}

/** Personal memory controls + data export + account deletion. */
export function MemoryPanel({ api, onDeleted }: { api: Api; onDeleted: () => void }) {
  const [m, setM] = useState<any>({ items: [], personalization_enabled: true }), [msg, setMsg] = useState("");
  const load = useCallback(async () => { try { setM(await api("/api/memory")); } catch (e: any) { setMsg(e.message); } }, []);
  useEffect(() => { load(); }, []);
  const act = async (fn: () => Promise<any>) => { try { setMsg(""); await fn(); await load(); } catch (e: any) { setMsg(e.message); } };
  const exportData = () => act(async () => { const d = await api("/api/me/export"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); a.download = "my-data.json"; a.click(); });
  return <div className="card"><h3>זיכרון אישי ופרטיות</h3>
    <label><input type="checkbox" checked={m.personalization_enabled} onChange={e => act(() => api("/api/memory/preferences", { method: "PUT", body: { personalization_enabled: e.target.checked } }))} /> התאמה אישית פעילה</label>
    {m.items.map((i: any) => <div key={i.id}>{i.kind === "saved" ? "👍" : "👎"} {i.text} <button className="ghost" onClick={() => act(() => api(`/api/memory/${i.id}`, { method: "DELETE" }))}>מחק</button></div>)}
    <button className="ghost" onClick={() => act(() => api("/api/memory", { method: "DELETE" }))}>מחק את כל הזיכרון</button>
    <button className="ghost" onClick={exportData}>ייצוא כל הנתונים שלי</button>
    <button className="ghost" onClick={() => { if (confirm("למחוק את החשבון וכל הנתונים? הפעולה אינה הפיכה.")) act(async () => { await api("/api/me", { method: "DELETE" }); onDeleted(); }); }}>מחק חשבון</button>
    <div className="err">{msg}</div></div>;
}

export function Notifications({ api }: { api: Api }) {
  const [n, setN] = useState<any>({ unread: 0, items: [] });
  const load = useCallback(async () => { try { setN(await api("/api/notifications")); } catch {} }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  return <div className="card"><h3>התראות ({n.unread} חדשות)</h3>
    {n.items.slice(0, 8).map((x: any) => <div key={x.id} style={{ opacity: x.read ? 0.6 : 1 }}>{x.title} {x.body} {!x.read && <button className="ghost" onClick={async () => { await api(`/api/notifications/${x.id}/read`, { method: "POST" }); load(); }}>סמן כנקרא</button>}</div>)}</div>;
}

/** Admin command center: overview, queues, sources, audit log, feature flags (admins only). */
export function AdminPanel({ api, role }: { api: Api; role: string }) {
  const [tab, setTab] = useState("overview"), [d, setD] = useState<any>({}), [msg, setMsg] = useState("");
  const isAdmin = role === "admin" || role === "super_admin";
  const load = useCallback(async () => {
    try {
      const calls: Record<string, string> = { overview: "/api/admin/overview", jobs: "/api/admin/jobs", sources: "/api/admin/sources", audit: "/api/admin/audit-logs", events: "/api/agents/events", metrics: "/api/admin/metrics", settings: "/api/admin/system-settings" };
      if (!(tab in calls) || (!isAdmin && ["audit", "settings", "metrics"].includes(tab))) return;
      setD({ ...d, [tab]: await api(calls[tab]) });
    } catch (e: any) { setMsg(e.message); }
  }, [tab]);
  useEffect(() => { load(); }, [tab]);
  const toggle = async (k: string, v: boolean) => { try { setMsg(""); setD({ ...d, settings: await api("/api/admin/system-settings", { method: "PATCH", body: { flags: { [k]: v } } }) }); } catch (e: any) { setMsg(e.message); } };
  const tabs = [["overview", "סקירה"], ["jobs", "תורים"], ["sources", "מקורות"], ["events", "אירועי סוכנים"]].concat(isAdmin ? [["audit", "יומן ביקורת"], ["metrics", "מטריקות"], ["settings", "הגדרות"]] : []);
  const o = d.overview;
  return <div className="card"><h3>מרכז ניהול</h3>
    {tabs.map(([k, v]) => <button key={k} className={tab === k ? "" : "ghost"} onClick={() => setTab(k)}>{v}</button>)}
    <div className="err">{msg}</div>
    {tab === "overview" && o && <div className="grid">{[["משתמשים", o.users], ["מנויים פעילים", o.active_subscriptions], ["הכנסה חודשית (₪)", o.mrr_ils], ["חיפושים פעילים", o.active_searches], ["מודעות", o.listings], ["מקורות בשגיאה", o.sources_in_error]].map(([k, v]: any) => <div className="card" key={k}>{k}<div className="score">{v}</div></div>)}
      <div className="card">תור: {Object.entries(o.queue || {}).map(([k, v]) => `${k}=${v}`).join(" · ") || "ריק"}</div></div>}
    {tab === "jobs" && <table><tbody>{(d.jobs || []).map((j: any) => <tr key={j.id}><td>{j.kind}</td><td>{j.status}</td><td>{j.attempts}</td><td>{j.last_error}</td><td>{j.status === "dead" && isAdmin && <button className="ghost" onClick={async () => { await api(`/api/admin/jobs/${j.id}/retry`, { method: "POST" }); load(); }}>נסה שוב</button>}</td></tr>)}</tbody></table>}
    {tab === "sources" && <table><tbody>{(d.sources || []).map((s: any) => <tr key={s.id}><td>{s.url}</td><td>{s.status}</td><td>{s.last_error}</td></tr>)}</tbody></table>}
    {tab === "events" && <table><tbody>{(d.events || []).map((e: any, i: number) => <tr key={i}><td>{e.agent}</td><td>{e.event}</td><td>{e.duration_ms ? Math.round(e.duration_ms) + "ms" : ""}</td><td>{e.detail}</td></tr>)}</tbody></table>}
    {tab === "audit" && <table><tbody>{(d.audit || []).map((a: any, i: number) => <tr key={i}><td>{a.at}</td><td>{a.action}</td><td>{a.target}</td></tr>)}</tbody></table>}
    {tab === "metrics" && d.metrics && <pre>{JSON.stringify(d.metrics, null, 2)}</pre>}
    {tab === "settings" && d.settings && <div>
      {Object.entries(d.settings.flags).map(([k, v]: any) => <label key={k} style={{ display: "block" }}><input type="checkbox" checked={v} onChange={e => toggle(k, e.target.checked)} /> {{ llm_extraction: "חילוץ באמצעות LLM (דורש OPENAI_API_KEY בתשלום)", pgvector: "זיכרון pgvector (דורש Postgres עם USE_PGVECTOR=1)", maintenance_mode: "מצב תחזוקה" }[k as string] || k}</label>)}
      <div>LLM מוגדר בשרת: {d.settings.capabilities.llm_configured ? "כן" : "לא"} · pgvector בסביבה: {d.settings.capabilities.pgvector_env ? "כן" : "לא"}</div></div>}
  </div>;
}
