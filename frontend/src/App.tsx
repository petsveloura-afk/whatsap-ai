import { useEffect, useState, useCallback } from "react";
import { Wizard, SourcesPanel, MemoryPanel, Notifications, AdminPanel } from "./panels";
import { GrowthPanel } from "./growth";
import { AssistantPanel } from "./assistant";
import { AgentPanel, DiscoverPanel } from "./agent";
import { Icon, Opportunities } from "./listings";
import { ProPanel } from "./pro";
import { fmtPrice } from "./lib/search";
import { ProfilePanel } from "./profile";
import { GuidePanel } from "./guide";
import { ConnectPanel } from "./connect";
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
  return <div className="wrap landing"><div className="orb-bg" aria-hidden="true" />
    <div className="land-cols"><div className="hero"><span className="eyebrow"><Icon n="spark" /> SMART SNIPER AI</span><h1>אל תחפש את ההזדמנות הבאה שלך. תן ל-AI למצוא אותה.</h1>
      <p>Smart Sniper AI סורק מקורות מידע מורשים, מנתח מודעות בזמן אמת ומציג לך את ההזדמנויות שבאמת מתאימות למה שאתה מחפש, כולל כפתורי התקשרות ווטסאפ בלחיצה אחת.</p></div>
    <form className="card auth" onSubmit={e => { e.preventDefault(); go(); }}><h3>{mode === "login" ? "התחברות" : "הרשמה"}</h3>
      <input placeholder="אימייל" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} /><input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder="סיסמה (10+ תווים)" value={pw} onChange={e => setPw(e.target.value)} />
      <button type="submit">{mode === "login" ? "כניסה" : "מתחילים למצוא הזדמנויות"}</button>
      <button type="button" className="ghost" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "אין חשבון? הרשמה" : "יש חשבון? כניסה"}</button>
      {mode === "login" && <button type="button" className="ghost" onClick={forgot}>שכחתי סיסמה</button>}<div className="err" role="alert">{msg}</div></form></div>
    <div className="grid steps"><div className="card"><b>1. מגדירים</b>מה מחפשים, תקציב ואזור.</div><div className="card"><b>2. המערכת מנתחת</b>חילוץ, סינון כפילויות וציון התאמה.</div><div className="card"><b>3. מקבלים בזמן אמת</b>התראות דרך האתר, Telegram ו-WhatsApp.</div><div className="card"><b>4. יוצרים קשר מיד</b>טלפון, וואטסאפ, אימייל וקישור למודעה על כל תוצאה.</div></div>
    <div className="feat">
      <div className="card"><Icon n="bot" /><b>סוכן אישי</b><p>צ׳אט שמבין מה אתה מחפש, מבצע פעולות וזוכר העדפות.</p></div>
      <div className="card"><Icon n="radar" /><b>גילוי מהרשת</b><p>חיפוש דרך מנוע חיפוש רשמי והדבקה מרובה של מודעות.</p></div>
      <div className="card"><Icon n="shield" /><b>פרטיות ואבטחה</b><p>הנתונים שלך הם שלך: ייצוא ומחיקה בלחיצה.</p></div>
    </div></div>;
}
function Reset({ token }: any) {
  const [pw, setPw] = useState(""), [msg, setMsg] = useState("");
  const go = async () => { try { await api("/api/auth/reset-password", { method: "POST", body: { token, password: pw } }); setMsg("הסיסמה עודכנה. אפשר להתחבר."); } catch (e: any) { setMsg(e.message); } };
  return <div className="wrap card"><h3>איפוס סיסמה</h3><input type="password" placeholder="סיסמה חדשה" value={pw} onChange={e => setPw(e.target.value)} /><button onClick={go}>עדכן</button> <a href="/">חזרה</a><div>{msg}</div></div>;
}
const TABS: [string, string, string][] = [["overview", "סקירה", "home"], ["opps", "הזדמנויות", "target"], ["agent", "הסוכן", "bot"], ["discover", "חיפושים ומקורות", "radar"], ["pro", "כלי פרו", "bolt"], ["account", "החשבון", "user"]];
function Dash({ user, onLogout }: any) {
  const [searches, setSearches] = useState<any[]>([]), [listings, setListings] = useState<any[]>([]), [ov, setOv] = useState<any>({}), [agents, setAgents] = useState<any[]>([]);
  const [sub, setSub] = useState<any>({}), [users, setUsers] = useState<any[]>([]), [msg, setMsg] = useState(""), [sid, setSid] = useState(""), [text, setText] = useState("");
  const [f, setF] = useState({ name: "", category: "real_estate", location: "", max_price: "" }), [live, setLive] = useState(false), [toast, setToast] = useState("");
  const isAdmin = ["admin", "super_admin", "support"].includes(user.role);
  const tabs = isAdmin ? [...TABS, ["admin", "ניהול", "settings"] as [string, string, string]] : TABS;
  const [tab, setTab] = useState(() => { const h = location.hash.replace("#", ""); return tabs.some(t => t[0] === h) ? h : "overview"; });
  const go = (t: string) => { setTab(t); try { history.replaceState(null, "", "#" + t); } catch {} window.scrollTo({ top: 0 }); };
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 2600); };
  // v3.16 keyboard shortcuts: Alt+Shift+1..9 jumps to the n-th tab (Alt+digit alone is taken by some browsers for their own tabs)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || !e.shiftKey || e.ctrlKey || e.metaKey) return;
      const m = /^Digit([1-9])$/.exec(e.code), t = m && tabs[Number(m[1]) - 1];
      if (t) { e.preventDefault(); go(t[0]); }
    };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [isAdmin]);
  const load = useCallback(async () => {
    try {
      const [s, l, o, a, b] = await Promise.all([api("/api/searches"), api("/api/listings"), api("/api/dashboard/overview"), api("/api/agents"), api("/api/billing/subscription")]);
      setSearches(s); setListings(l); setOv(o); setAgents(a); setSub(b); setSid((cur: string) => s.some((x: any) => x.id === cur) ? cur : (s[0]?.id || ""));
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
      ws.onmessage = m => { if (JSON.parse(m.data).type?.startsWith("listing.")) { load(); flash("הזדמנות חדשה התקבלה"); } };
      ws.onclose = () => { setLive(false); if (!dead) t = setTimeout(open, Math.min(30000, 1000 * 2 ** n++)); };
    };
    open(); return () => { dead = true; clearTimeout(t); ws && ws.close(); };
  }, []);
  const act = async (fn: () => Promise<any>) => { try { setMsg(""); await fn(); await load(); } catch (e: any) { setMsg(e.message); } };
  const create = () => act(() => api("/api/searches", { method: "POST", body: { name: f.name, category: f.category, location: f.location || null, max_price: f.max_price ? Number(f.max_price) : null } }));
  const ingest = () => act(async () => { const r = await api("/api/listings/ingest", { method: "POST", body: { search_id: sid, text } }); setMsg(`נקלט: ${r.status}, ציון ${r.score}`); setText(""); });
  const logout = async () => { try { await api("/api/auth/logout", { method: "POST", body: { refresh_token: sessionStorage.getItem("rt") } }); } catch {} sessionStorage.removeItem("rt"); access = ""; onLogout(); };
  const newCount = listings.filter(l => l.status === "new").length;
  const top = [...listings].filter(l => l.status === "new" || l.status === "saved").sort((a, b) => b.score - a.score).slice(0, 4);
  const show = (t: string) => ({ hidden: tab !== t, role: "tabpanel" as const, "aria-label": tabs.find(x => x[0] === t)?.[1] });
  const planLabel = ({ starter: "Starter", pro: "Pro", vip: "VIP" } as any)[sub.plan] || sub.plan || "-";
  const kpis: [string, any, string, string][] = [["סה״כ הזדמנויות", ov.total_listings, "layers", "var(--cy)"], ["התאמות גבוהות", ov.high_quality, "star", "var(--gr)"], ["סוננו", ov.filtered_out, "shield", "var(--pk)"], ["חיפושים פעילים", ov.active_searches, "radar", "var(--vi)"]];
  return <div className="shell">
    <a className="skip-link" href="#main" onClick={e => { e.preventDefault(); document.getElementById("main")?.focus(); }}>דלג לתוכן הראשי</a>
    <aside className="side"><h1 className="brand">Smart Sniper AI</h1>
      <nav className="nav" aria-label="ניווט ראשי">{tabs.map(([k, v, ic]) => <button key={k} aria-current={tab === k ? "page" : undefined} onClick={() => go(k)}><Icon n={ic} />{v}{k === "opps" && newCount > 0 && <span className="badge">{newCount}</span>}</button>)}</nav>
      <div className="me-box"><b>{user.email}</b><span>חבילה: <span className="plan">{planLabel}</span></span><span className="live"><i className={"dot " + (live ? "on" : "off")} /><span className={live ? "ok" : "err"}>{live ? "חי" : "לא מחובר"}</span></span></div>
      <button className="ghost side-foot" onClick={logout}><Icon n="logout" /> יציאה</button></aside>
    <main className="main" id="main" tabIndex={-1}>
      <header className="top"><div className="who"><span className="live"><i className={"dot " + (live ? "on" : "off")} /><span className={live ? "ok" : "err"}>{live ? "חי" : "לא מחובר"}</span></span><span>{user.email}</span><span>חבילה: <span className="plan">{planLabel}</span></span></div>
        <div className="who"><button className="ghost sm" onClick={load}><Icon n="bolt" /> רענן</button><button className="ghost sm" onClick={logout}><Icon n="logout" /> יציאה</button></div></header>
      <div className="err" role="alert">{msg}</div>

      <section {...show("overview")}>
        <div className="tab-h"><div><h2>שלום, הנה מה שקורה עכשיו</h2><p>סיכום חי של ההזדמנויות, הסוכנים וההתראות שלך.</p></div><button onClick={() => go("opps")}><Icon n="target" /> לכל ההזדמנויות</button></div>
        <div className="kpis">{kpis.map(([k, v, ic, col]) => <div className="kpi" key={k} style={{ "--k": col } as any}><span><Icon n={ic} />{k}</span><b>{v ?? "-"}</b></div>)}</div>
        <div className="cols">
          <div className="card"><h3>ההזדמנויות המובילות</h3>
            {top.length === 0 && <div className="empty-big"><div className="orb" aria-hidden="true" /><h3>עוד אין התאמות</h3><p>צור חיפוש והבא מודעות כדי להתחיל.</p><button onClick={() => go("discover")}><Icon n="radar" /> להבאת הזדמנויות</button></div>}
            {top.map(l => <div className="found-row" key={l.id}><span className="score" style={{ "--p": l.score } as any}>{l.score}</span><span className="fr-main"><b>{l.title || l.extracted.location || "הזדמנות"}</b><span className="faint">{l.extracted.location || "?"} · {l.extracted.rooms ?? "?"} חד׳ · {fmtPrice(l.extracted.price, l.extracted.currency)}</span></span><span className="fr-act">
              {l.contact?.phones?.[0] && <a className="btn call sm" href={"tel:" + l.contact.phones[0].tel}><Icon n="phone" />התקשר</a>}
              {l.contact?.phones?.[0]?.whatsapp && <a className="btn wa sm" href={l.contact.phones[0].whatsapp} target="_blank" rel="noopener noreferrer"><Icon n="chat" />וואטסאפ</a>}
              {l.source_url && <a className="btn src sm" href={l.source_url} target="_blank" rel="noopener noreferrer nofollow"><Icon n="link" />מקור</a>}</span></div>)}
          </div>
          <Notifications api={api} />
        </div>
        <div className="card"><h3>סוכנים (טלמטריה חיה)</h3><div className="telemetry">{agents.map(a => <div className="tele" key={a.name}><span className="nm">{a.name}<i className={"dot " + (a.status === "IDLE" || a.status === "idle" ? "" : a.errors ? "off" : "on")} /></span><span className="mt"><span>{a.status}</span><span>{a.processed} רשומות</span><span>{a.errors} שגיאות</span><span>{a.avg_ms ?? "-"}ms</span></span><span className="bar"><i style={{ inlineSize: Math.min(100, (a.processed || 0) * 4) + "%" }} /></span></div>)}</div></div>
      </section>

      <section {...show("opps")}>
        <div className="tab-h"><div><h2>הזדמנויות</h2><p>כל תוצאה עם ציון, הסבר, וכפתורי יצירת קשר: התקשר, וואטסאפ, אימייל או פתיחת המודעה במקור.</p></div></div>
        <Opportunities listings={listings} searches={searches} api={api} act={act} onToast={flash} goDiscover={() => go("discover")} />
      </section>

      <section {...show("agent")}>
        <div className="tab-h"><div><h2>הסוכן שלי</h2><p>שאל, בקש פעולות, והסוכן יעדכן את החיפושים וההזדמנויות בשבילך.</p></div></div>
        <div className="cols"><AgentPanel api={api} onChanged={load} /><AssistantPanel api={api} searches={searches} /></div>
      </section>

      <section {...show("discover")}>
        <div className="tab-h"><div><h2>חיפושים ומקורות</h2><p>הגדר מה אתה מחפש, הבא מודעות מהרשת או הדבק אותן, וחבר מקורות RSS.</p></div></div>
        <div className="cols">
          <div className="card"><h3>חיפוש חדש</h3><div className="form-grid"><input placeholder="שם" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /><select value={f.category} onChange={e => setF({ ...f, category: e.target.value })}><option value="real_estate">נדל״ן</option><option value="vehicles">רכב</option><option value="electronics">אלקטרוניקה</option></select>
            <input placeholder="מיקום" value={f.location} onChange={e => setF({ ...f, location: e.target.value })} /><input placeholder="מחיר מקסימלי" inputMode="numeric" value={f.max_price} onChange={e => setF({ ...f, max_price: e.target.value })} /></div>
            <button onClick={create}>צור</button>
            {searches.map(s => <div className="srow" key={s.id}><span className="nm">{s.name}</span><span className={"status " + (s.active ? "new" : "")}>{s.active ? "פעיל" : "מושהה"}</span><button className="ghost sm" onClick={() => act(() => api(`/api/searches/${s.id}/${s.active ? "pause" : "resume"}`, { method: "POST" }))}>{s.active ? "השהה" : "המשך"}</button> <button className="danger sm" onClick={() => act(() => api(`/api/searches/${s.id}`, { method: "DELETE" }))}>מחק</button></div>)}</div>
          <Wizard api={api} onCreated={load} />
        </div>
        <DiscoverPanel api={api} searches={searches} onChanged={load} />
        <div className="card"><h3>הדבק מודעה לניתוח</h3><select value={sid} onChange={e => setSid(e.target.value)}>{searches.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select><br /><textarea rows={3} style={{ width: "100%" }} value={text} onChange={e => setText(e.target.value)} placeholder="דירת 3 חדרים בחולון, משופצת, 5,200 ש״ח. לפרטים 050-123-4567" /><button onClick={ingest} disabled={!sid || text.length < 5}>נתח</button>
          <p className="faint">טיפ: הדבק את המודעה כולל הטלפון, ונציג לך כפתורי התקשרות ווטסאפ.</p></div>
        <SourcesPanel api={api} searches={searches} />
        <div className="card"><h3>סריקה מורחבת</h3><p className="faint">שאילתות חכמות בכמה ניסוחים ובכל אתרי המודעות, דירוג מחדש וסינון זבל.</p><button onClick={() => go("pro")}><Icon n="radar" /> לסריקה המורחבת</button></div>
      </section>

      <section {...show("pro")}>
        <div className="tab-h"><div><h2>כלי פרו</h2><p>סריקה מורחבת, ניתוח הונאות ומשא ומתן, מחשבונים, מעקב ולקוחות ודוחות ממותגים.</p></div></div>
        <ProPanel api={api} listings={listings} searches={searches} isAdmin={isAdmin} onChanged={load} />
      </section>

      <section {...show("account")}>
        <div className="tab-h"><div><h2>החשבון</h2><p>פרופיל, מנוי, פרטיות, זיכרון, מדריך וכלים למפתחים.</p></div></div>
        <ProfilePanel api={api} onNavigate={go} />
        <ConnectPanel api={api} searches={searches} />
        <div className="card"><h3>מנוי</h3><div className="plans">{[["pro", "Pro", "99", true], ["vip", "VIP", "149", false]].map(([k, n, p, hot]: any) => <div className={"plan-card" + (hot ? " hot" : "")} key={k}><b>{n}</b><span className="pr">{p} ₪</span><button onClick={() => act(async () => { const r = await api("/api/billing/checkout", { method: "POST", body: { plan: k } }); location.href = r.approve_url; })}>{n} {p} ₪</button></div>)}</div><div className="faint">החיוב דרך PayPal; החשבון מופעל רק לאחר אישור שרת מאומת.</div></div>
        <MemoryPanel api={api} onDeleted={() => { sessionStorage.removeItem("rt"); access = ""; onLogout(); }} />
        <GrowthPanel api={api} />
        <GuidePanel onNavigate={go} tabs={tabs} />
        <div className="card install"><Icon n="download" /><div>התקנה כאפליקציה: ב-Android/Chrome תפריט ← "התקן אפליקציה". ב-iPhone: שיתוף ← "הוסף למסך הבית".</div></div>
      </section>

      {isAdmin && <section {...show("admin")}>
        <div className="tab-h"><div><h2>ניהול</h2><p>מרכז ניהול, תורים, דגלי פיצ׳רים ומשתמשים.</p></div></div>
        <AdminPanel api={api} role={user.role} />
        <div className="card"><h3>ניהול משתמשים</h3><table><tbody>{users.map(u => <tr key={u.id}><td>{u.email}</td><td>{u.role}</td><td>{u.is_active ? "פעיל" : "מושבת"}</td><td><button className="ghost sm" onClick={() => act(() => api(`/api/admin/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }))}>{u.is_active ? "השבת" : "הפעל"}</button></td></tr>)}</tbody></table></div>
      </section>}
    </main>
    {toast && <div className="toast" role="status">{toast}</div>}
  </div>;
}
export default function App() {
  const [user, setUser] = useState<any>(null), [ready, setReady] = useState(false);
  const rt = location.pathname === "/reset" ? new URLSearchParams(location.search).get("token") : null;
  useEffect(() => { refresh().then(ok => ok ? api("/api/auth/me").then(setUser) : null).catch(() => {}).finally(() => setReady(true)); }, []);
  if (rt) return <Reset token={rt} />;
  if (!ready) return null;
  return user ? <Dash user={user} onLogout={() => setUser(null)} /> : <Landing onAuth={setUser} />;
}
