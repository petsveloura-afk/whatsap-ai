import { useEffect, useState, useCallback } from "react";
import { Wizard, SourcesPanel, MemoryPanel, Notifications, AdminPanel } from "./panels";
import { GrowthPanel } from "./growth";
import { AssistantPanel } from "./assistant";
import { AgentPanel } from "./agent";
const API: string = (import.meta as any).env.VITE_API_URL || "";
let access = "";
async function refresh(): Promise<boolean> {
  const rt = sessionStorage.getItem("rt"); if (!rt) return false;
  const r = await fetch(API + "/api/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }) });
  if (!r.ok) { sessionStorage.removeItem("rt"); return false; }
  const d = await r.json(); access = d.access_token; sessionStorage.setItem("rt", d.refresh_token); return true;
}
async function api(path: string, o: any = {}, retry = true): Promise<any> {
  const r = await fetch(API + path, { method: o.method, body: o.body ? JSON.stringify(o.body) : undefined, headers: { "Content-Type": "application/json", ...(access ? { Authorization: "Bearer " + access } : {}) } });
  if (r.status === 401 && retry && (await refresh())) return api(path, o, false);
  if (!r.ok) { const d = (await r.json().catch(() => ({}))).detail; throw new Error(typeof d === "string" ? d : "קלט לא תקין"); }
  return r.status === 204 ? null : r.json();
}
async function login(email: string, password: string) {
  const d = await api("/api/auth/login", { method: "POST", body: { email, password } }); access = d.access_token; sessionStorage.setItem("rt", d.refresh_token);
  return api("/api/auth/me");
}
function Landing({ onAuth }: any) {
  const [mode, setMode] = useState("login"), [email, setEmail] = useState(""), [pw, setPw] = useState(""), [msg, setMsg] = useState("");
  const go = async () => { try { setMsg(""); if (mode === "register") await api("/api/auth/register", { method: "POST", body: { email, password: pw } }); onAuth(await login(email, pw)); } catch (e: any) { setMsg(e.message); } };
  const forgot = async () => { try { await api("/api/auth/forgot-password", { method: "POST", body: { email } }); setMsg("אם החשבון קיים, נשלח מייל איפוס"); } catch (e: any) { setMsg(e.message); } };
  return <div className="wrap landing"><div className="hero"><h1>אל תחפש את ההזדמנות הבאה שלך. תן ל-AI למצוא אותה.</h1>
    <p>Smart Sniper AI סורק מקורות מידע מורשים, מנתח מודעות בזמן אמת ומציג לך את ההזדמנויות שבאמת מתאימות למה שאתה מחפש.</p></div>
    <div className="grid steps"><div className="card"><b>1. מגדירים</b><br />מה מחפשים, תקציב ואזור.</div><div className="card"><b>2. המערכת מנתחת</b><br />חילוץ, סינון כפילויות וציון התאמה.</div><div className="card"><b>3. מקבלים בזמן אמת</b><br />התראות דרך האתר, Telegram ו-WhatsApp.</div></div>
    <div className="card auth"><h3>{mode === "login" ? "התחברות" : "הרשמה"}</h3>
      <input placeholder="אימייל" value={email} onChange={e => setEmail(e.target.value)} /><input type="password" placeholder="סיסמה (10+ תווים)" value={pw} onChange={e => setPw(e.target.value)} />
      <button onClick={go}>{mode === "login" ? "כניסה" : "מתחילים למצוא הזדמנויות"}</button>
      <button className="ghost" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "אין חשבון? הרשמה" : "יש חשבון? כניסה"}</button>
      {mode === "login" && <button className="ghost" onClick={forgot}>שכחתי סיסמה</button>}<div className="err">{msg}</div></div></div>;
}
function Reset({ token }: any) {
  const [pw, setPw] = useState(""), [msg, setMsg] = useState("");
  const go = async () => { try { await api("/api/auth/reset-password", { method: "POST", body: { token, password: pw } }); setMsg("הסיסמה עודכנה. אפשר להתחבר."); } catch (e: any) { setMsg(e.message); } };
  return <div className="wrap card"><h3>איפוס סיסמה</h3><input type="password" placeholder="סיסמה חדשה" value={pw} onChange={e => setPw(e.target.value)} /><button onClick={go}>עדכן</button> <a href="/">חזרה</a><div>{msg}</div></div>;
}
function Dash({ user, onLogout }: any) {
  const [searches, setSearches] = useState<any[]>([]), [listings, setListings] = useState<any[]>([]), [ov, setOv] = useState<any>({}), [agents, setAgents] = useState<any[]>([]);
  const [sub, setSub] = useState<any>({}), [users, setUsers] = useState<any[]>([]), [msg, setMsg] = useState(""), [sid, setSid] = useState(""), [text, setText] = useState("");
  const [f, setF] = useState({ name: "", category: "real_estate", location: "", max_price: "" }), [live, setLive] = useState(false);
  const isAdmin = ["admin", "super_admin", "support"].includes(user.role);
  const load = useCallback(async () => {
    try {
      const [s, l, o, a, b] = await Promise.all([api("/api/searches"), api("/api/listings"), api("/api/dashboard/overview"), api("/api/agents"), api("/api/billing/subscription")]);
      setSearches(s); setListings(l); setOv(o); setAgents(a); setSub(b); if (!sid && s[0]) setSid(s[0].id);
      if (isAdmin) setUsers(await api("/api/admin/users"));
    } catch (e: any) { setMsg(e.message); }
  }, [sid, isAdmin]);
  useEffect(() => { load(); }, []);
  useEffect(() => {
    let ws: WebSocket, t: any, n = 0, dead = false;
    const open = () => {
      const base = API ? API.replace(/^http/, "ws") : location.origin.replace(/^http/, "ws");
      ws = new WebSocket(base + "/ws?token=" + access);
      ws.onopen = () => { setLive(true); n = 0; };
      ws.onmessage = m => { if (JSON.parse(m.data).type?.startsWith("listing.")) load(); };
      ws.onclose = () => { setLive(false); if (!dead) t = setTimeout(open, Math.min(30000, 1000 * 2 ** n++)); };
    };
    open(); return () => { dead = true; clearTimeout(t); ws && ws.close(); };
  }, []);
  const act = async (fn: () => Promise<any>) => { try { setMsg(""); await fn(); await load(); } catch (e: any) { setMsg(e.message); } };
  const create = () => act(() => api("/api/searches", { method: "POST", body: { name: f.name, category: f.category, location: f.location || null, max_price: f.max_price ? Number(f.max_price) : null } }));
  const ingest = () => act(async () => { const r = await api("/api/listings/ingest", { method: "POST", body: { search_id: sid, text } }); setMsg(`נקלט: ${r.status}, ציון ${r.score}`); setText(""); });
  return <div className="wrap"><header className="top"><h1 className="brand">Smart Sniper AI</h1><div className="who">{user.email} · חבילה: {sub.plan} · <span className={live ? "ok" : "err"}>{live ? "חי" : "לא מחובר"}</span> <button className="ghost" onClick={async () => { try { await api("/api/auth/logout", { method: "POST", body: { refresh_token: sessionStorage.getItem("rt") } }); } catch {} sessionStorage.removeItem("rt"); access = ""; onLogout(); }}>יציאה</button></div></header>
    <div className="err">{msg}</div>
    <div className="grid stats">{[["סה״כ הזדמנויות", ov.total_listings], ["התאמות גבוהות", ov.high_quality], ["סוננו", ov.filtered_out], ["חיפושים פעילים", ov.active_searches]].map(([k, v]: any) => <div className="card stat" key={k}><span>{k}</span><b>{v ?? "-"}</b></div>)}</div>
    <div className="card"><h3>סוכנים (טלמטריה חיה)</h3><table><tbody>{agents.map(a => <tr key={a.name}><td>{a.name}</td><td>{a.status}</td><td>{a.processed} רשומות</td><td>{a.errors} שגיאות</td><td>{a.avg_ms ?? "-"}ms</td></tr>)}</tbody></table></div>
    <AgentPanel api={api} onChanged={load} />
    <Notifications api={api} />
    <Wizard api={api} onCreated={load} />
    <AssistantPanel api={api} searches={searches} />
    <div className="card"><h3>חיפוש חדש</h3><input placeholder="שם" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /><select value={f.category} onChange={e => setF({ ...f, category: e.target.value })}><option value="real_estate">נדל״ן</option><option value="vehicles">רכב</option><option value="electronics">אלקטרוניקה</option></select>
      <input placeholder="מיקום" value={f.location} onChange={e => setF({ ...f, location: e.target.value })} /><input placeholder="מחיר מקסימלי" value={f.max_price} onChange={e => setF({ ...f, max_price: e.target.value })} /><button onClick={create}>צור</button>
      {searches.map(s => <div key={s.id}>{s.name} ({s.active ? "פעיל" : "מושהה"}) <button className="ghost" onClick={() => act(() => api(`/api/searches/${s.id}/${s.active ? "pause" : "resume"}`, { method: "POST" }))}>{s.active ? "השהה" : "המשך"}</button> <button className="ghost" onClick={() => act(() => api(`/api/searches/${s.id}`, { method: "DELETE" }))}>מחק</button></div>)}</div>
    <div className="card"><h3>הדבק מודעה לניתוח</h3><select value={sid} onChange={e => setSid(e.target.value)}>{searches.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select><br /><textarea rows={3} style={{ width: "100%" }} value={text} onChange={e => setText(e.target.value)} placeholder="דירת 3 חדרים בחולון, משופצת, 5,200 ש״ח" /><button onClick={ingest} disabled={!sid || text.length < 5}>נתח</button></div>
    <h3>הזדמנויות</h3>{listings.map(l => <div className="card listing" key={l.id}><span className="score" style={{ "--p": l.score } as any} aria-label={`התאמה ${l.score}%`}>{l.score}</span> {l.extracted.location || "?"} · {l.extracted.rooms ?? "?"} חד׳ · {l.extracted.price ?? "?"} {l.extracted.currency || ""} · {l.status}
      {l.risks.map((r: string) => <div className="risk" key={r}>⚠ {r}</div>)}
      {["save:שמור", "reject:דחה", "contacted:יצרתי קשר"].map(x => { const [k, v] = x.split(":"); return <button className="ghost" key={k} onClick={() => act(() => api(`/api/listings/${l.id}/${k}`, { method: "POST" }))}>{v}</button>; })}</div>)}
    <SourcesPanel api={api} searches={searches} />
    <GrowthPanel api={api} />
    <MemoryPanel api={api} onDeleted={() => { sessionStorage.removeItem("rt"); access = ""; onLogout(); }} />
    <div className="card"><h3>מנוי</h3>{["pro:Pro 99 ₪", "vip:VIP 149 ₪"].map(x => { const [k, v] = x.split(":"); return <button key={k} onClick={() => act(async () => { const r = await api("/api/billing/checkout", { method: "POST", body: { plan: k } }); location.href = r.approve_url; })}>{v}</button>; })}<div>החיוב דרך PayPal; החשבון מופעל רק לאחר אישור שרת מאומת.</div></div>
    {isAdmin && <AdminPanel api={api} role={user.role} />}
    {isAdmin && <div className="card"><h3>ניהול משתמשים</h3><table><tbody>{users.map(u => <tr key={u.id}><td>{u.email}</td><td>{u.role}</td><td>{u.is_active ? "פעיל" : "מושבת"}</td><td><button className="ghost" onClick={() => act(() => api(`/api/admin/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }))}>{u.is_active ? "השבת" : "הפעל"}</button></td></tr>)}</tbody></table></div>}
    <div className="card">התקנה כאפליקציה: ב-Android/Chrome תפריט ← "התקן אפליקציה". ב-iPhone: שיתוף ← "הוסף למסך הבית".</div></div>;
}
export default function App() {
  const [user, setUser] = useState<any>(null), [ready, setReady] = useState(false);
  const rt = location.pathname === "/reset" ? new URLSearchParams(location.search).get("token") : null;
  useEffect(() => { refresh().then(ok => ok ? api("/api/auth/me").then(setUser) : null).catch(() => {}).finally(() => setReady(true)); }, []);
  if (rt) return <Reset token={rt} />;
  if (!ready) return null;
  return user ? <Dash user={user} onLogout={() => setUser(null)} /> : <Landing onAuth={setUser} />;
}
