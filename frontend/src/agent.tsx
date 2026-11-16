import { useEffect, useRef, useState } from "react";
type Api = (path: string, o?: any) => Promise<any>;
type Msg = { role: "user" | "assistant"; content: string; actions?: { tool: string; summary: string }[]; mode?: string; error?: string };

const QUICK = [
  "מה ההזדמנויות הכי טובות עכשיו?",
  "צור חיפוש לדירת 3 חדרים בחולון עד 5,500",
  "תן לי סיכום של כל החיפושים שלי",
  "מה אתה זוכר עליי?",
];

/** The agent: chat that can read your data, act on it (searches, listings, sources) and remember you.
 *  Talks only to the new /api/agent/* endpoints. `onChanged` refreshes the dashboard after the agent changed something. */
export function AgentPanel({ api, onChanged }: { api: Api; onChanged?: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]), [text, setText] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const [st, setSt] = useState<any>(null), [mem, setMem] = useState<any[] | null>(null), [newMem, setNewMem] = useState("");
  const end = useRef<HTMLDivElement>(null);

  const loadStatus = () => api("/api/agent/status").then(setSt).catch(() => {});
  const loadMem = () => api("/api/agent/memory").then(d => setMem(d.items)).catch(e => setErr(e.message));
  useEffect(() => {
    loadStatus();
    api("/api/agent/history").then(d => setMsgs(d.items.map((m: any) => ({ role: m.role, content: m.content, actions: m.actions })))).catch(() => {});
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs, busy]);

  const send = async (q?: string) => {
    const m = (q ?? text).trim(); if (!m || busy) return;
    setErr(""); setText(""); setBusy(true); setMsgs(x => [...x, { role: "user", content: m }]);
    try {
      const r = await api("/api/agent/chat", { method: "POST", body: { message: m } });
      setMsgs(x => [...x, { role: "assistant", content: r.reply, actions: r.actions, mode: r.mode, error: r.error }]);
      if (r.actions?.length) { onChanged?.(); if (mem) loadMem(); }
      loadStatus();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const clearChat = async () => { try { await api("/api/agent/history", { method: "DELETE" }); setMsgs([]); } catch (e: any) { setErr(e.message); } };
  const addMem = async () => { try { await api("/api/agent/memory", { method: "POST", body: { text: newMem, kind: "preference" } }); setNewMem(""); loadMem(); loadStatus(); } catch (e: any) { setErr(e.message); } };
  const delMem = async (id: string) => { try { await api("/api/agent/memory/" + id, { method: "DELETE" }); loadMem(); loadStatus(); } catch (e: any) { setErr(e.message); } };

  const live = st?.mode === "agent";
  const banner = !st ? "" : live ? "" : !st.key_configured
    ? "מצב בסיסי: אני עונה מכללים מקומיים. להפעלת המוח החכם הוסף בשרת מפתח חינמי אחד או יותר (GEMINI_API_KEY, GROQ_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY ועוד), והדלק את הדגל llm_extraction בלשונית ניהול, לשונית הגדרות. פירוט בלשונית ניהול, לשונית מוחות."
    : "המפתחות קיימים. נשאר להדליק את הדגל llm_extraction בלשונית ניהול, לשונית הגדרות (או להגדיר BRAINS_AUTO_ENABLE=1 בשרת) כדי שהסוכן החכם יעבוד.";

  return (
    <section className="card agent" aria-label="הסוכן">
      <header className="agent-head">
        <div><h3>הסוכן שלי</h3><p>שואל, מנתח, מבצע פעולות ומתאים את עצמו אליך.</p></div>
        <span className={"pill " + (live ? "on" : "off")}>{live ? `חכם · ${st.provider ? st.provider + " / " : ""}${st.model}${st.brains?.length > 1 ? ` (+${st.brains.length - 1} גיבויים)` : ""}` : "בסיסי"}</span>
      </header>
      {banner && <div className="note">{banner}</div>}
      <div className="chat" role="log" aria-live="polite">
        {msgs.length === 0 && <div className="empty">עוד לא דיברנו. נסה אחת מהשאלות למטה, או כתוב משהו משלך.</div>}
        {msgs.map((m, i) => (
          <div key={i} className={"msg " + (m.role === "user" ? "me" : "bot")}>
            <div className="bubble">{m.content}</div>
            {m.error && <div className="note">המודל לא ענה ולכן קיבלת תשובה בסיסית. סיבה: {m.error}</div>}
            {m.actions && m.actions.length > 0 && <div className="acts">{m.actions.map((a, j) => <span key={j} className="chip">✓ {a.summary}</span>)}</div>}
          </div>
        ))}
        {busy && <div className="msg bot"><div className="bubble typing" aria-label="חושב"><i /><i /><i /></div></div>}
        <div ref={end} />
      </div>
      {err && <div className="err">{err}</div>}
      <div className="quick">{QUICK.map(q => <button key={q} className="ghost sm" disabled={busy} onClick={() => send(q)}>{q}</button>)}</div>
      <div className="composer">
        <textarea rows={1} value={text} placeholder="מה לעשות? למשל: תשמור את הדירה הכי טובה בחולון" maxLength={2000}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !(e.nativeEvent as any).isComposing) { e.preventDefault(); send(); } }} />
        <button onClick={() => send()} disabled={busy || !text.trim()}>שלח</button>
      </div>
      <div className="agent-foot">
        <button className="ghost sm" onClick={() => (mem ? setMem(null) : loadMem())}>{mem ? "סגור זיכרון" : `זיכרון${st ? ` (${st.memories})` : ""}`}</button>
        <button className="ghost sm" onClick={clearChat} disabled={!msgs.length}>נקה שיחה</button>
      </div>
      {mem && (
        <div className="memory">
          <p>מה שהסוכן יודע עליך. אפשר למחוק כל פריט, והוא נמחק גם כשמוחקים את החשבון.</p>
          {mem.length === 0 && <div className="empty">עדיין אין זיכרונות.</div>}
          {mem.map(m => <div className="mem-row" key={m.id}><span className="kind">{({ fact: "עובדה", preference: "העדפה", goal: "יעד", summary: "סיכום" } as any)[m.kind] || m.kind}</span><span>{m.text}</span><button className="ghost sm" onClick={() => delMem(m.id)} aria-label="מחק">מחק</button></div>)}
          <div className="composer"><input value={newMem} maxLength={500} placeholder="הוסף משהו שחשוב לזכור, למשל: מעדיף קומה גבוהה" onChange={e => setNewMem(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && newMem.trim().length > 2) addMem(); }} /><button className="ghost" onClick={addMem} disabled={newMem.trim().length < 3}>הוסף</button></div>
        </div>
      )}
    </section>
  );
}

/** Discovery: web search through an official search API (results are title + snippet + link, scored like any listing)
 *  and bulk paste of many listings at once. Talks to /api/agent/discover and /api/listings/ingest-bulk. */
export function DiscoverPanel({ api, searches, onChanged }: { api: Api; searches: any[]; onChanged?: () => void }) {
  const [sid, setSid] = useState(""), [q, setQ] = useState(""), [bulk, setBulk] = useState(""), [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false), [err, setErr] = useState(""), [web, setWeb] = useState<string | null | undefined>(undefined);
  useEffect(() => { api("/api/agent/status").then((s: any) => setWeb(s.web_search)).catch(() => setWeb(null)); }, []);
  useEffect(() => { if (!searches.some(s => s.id === sid)) setSid(searches[0]?.id || ""); }, [searches]);   // a deleted search must not stay selected
  const run = async (fn: () => Promise<any>) => { try { setErr(""); setBusy(true); setRes(await fn()); onChanged?.(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const web_ = () => run(() => api("/api/agent/discover", { method: "POST", body: { search_id: sid, query: q.trim() || null, limit: 10 } }));
  const bulk_ = () => run(() => api("/api/listings/ingest-bulk", { method: "POST", body: { search_id: sid, text: bulk } }));
  return (
    <section className="card discover" aria-label="גילוי הזדמנויות">
      <h3>הבא הזדמנויות</h3>
      <p>שתי דרכים חוקיות להכניס מודעות: חיפוש ברשת דרך מנוע חיפוש רשמי, או הדבקה של כמה מודעות יחד. כל אחת מנותחת ומדורגת.</p>
      <select value={sid} onChange={e => setSid(e.target.value)} aria-label="חיפוש">{searches.length === 0 && <option value="">צור קודם חיפוש</option>}{searches.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      <h4>חיפוש ברשת</h4>
      {web === null && <div className="note-l">חיפוש ברשת כבוי. כדי להפעיל: בשרת, הוסף מפתח חינמי אחד או יותר: TAVILY_API_KEY (app.tavily.com, בלי כרטיס אשראי), SERPER_API_KEY, EXA_API_KEY, JINA_API_KEY, BRAVE_API_KEY, או SEARXNG_URL. אפשר כמה מפתחות בשורה אחת מופרדים בפסיק, וכשמפתח נגמר המערכת עוברת לבא אחריו. פירוט בלשונית ניהול, לשונית מוחות.</div>}
      <div className="row"><input value={q} maxLength={200} placeholder="אופציונלי: מה לחפש? אם ריק, נבנה מהחיפוש שבחרת" onChange={e => setQ(e.target.value)} /><button onClick={web_} disabled={busy || !sid || !web}>{busy ? "מחפש..." : "חפש ברשת"}</button></div>
      <h4>הדבקה מרובה</h4>
      <textarea rows={4} value={bulk} onChange={e => setBulk(e.target.value)} placeholder={"הדבק כמה מודעות. הפרד ביניהן בשורה של --- או בשתי שורות ריקות."} />
      <button onClick={bulk_} disabled={busy || !sid || bulk.trim().length < 15}>נתח את כולן</button>
      {err && <div className="err">{err}</div>}
      {res && (
        <div className="found">
          <p>{res.results_found != null ? `נמצאו ${res.results_found} תוצאות. ` : `נותחו ${res.parsed} מודעות. `}התאמות חדשות: <b>{res.new}</b> · נפסלו: {res.rejected} · כבר קיימות: {res.duplicates}{res.irrelevant ? ` · כתבות שסוננו: ${res.irrelevant}` : ""}{res.errors ? ` · שגיאות: ${res.errors}` : ""}</p>
          {res.items?.map((i: any) => { const ph = i.contact?.phones?.[0]; return <div className="found-row" key={i.id}><span className="score" style={{ "--p": i.score } as any}>{i.score}</span>
            <span className="fr-main"><b>{i.title || i.location || "?"}</b><span className="faint">{i.location || "?"}{i.price ? ` · ${Math.round(i.price).toLocaleString()}` : ""}{ph ? ` · ${ph.display}` : ""}</span></span>
            <span className="fr-act">
              {ph && <a className="btn call sm" href={"tel:" + ph.tel}>התקשר</a>}
              {ph?.whatsapp && <a className="btn wa sm" href={ph.whatsapp} target="_blank" rel="noopener noreferrer">וואטסאפ</a>}
              {i.contact?.emails?.[0] && <a className="btn mail sm" href={"mailto:" + i.contact.emails[0]}>אימייל</a>}
              {i.url && <a className="btn src sm" href={i.url} target="_blank" rel="noopener noreferrer nofollow">פתח מקור</a>}</span></div>; })}
          {res.results_found != null && <p className="faint">תקצירי חיפוש חלקיים, לכן ציון נמוך לא תמיד אומר שהמודעה גרועה. פתח את המקור לפרטים.</p>}
        </div>
      )}
    </section>
  );
}
