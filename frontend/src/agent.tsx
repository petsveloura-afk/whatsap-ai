import { useEffect, useRef, useState } from "react";
type Api = (path: string, o?: any) => Promise<any>;
type Msg = { role: "user" | "assistant"; content: string; actions?: { tool: string; summary: string }[]; mode?: string };

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
      setMsgs(x => [...x, { role: "assistant", content: r.reply, actions: r.actions, mode: r.mode }]);
      if (r.actions?.length) { onChanged?.(); if (mem) loadMem(); }
      loadStatus();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const clearChat = async () => { try { await api("/api/agent/history", { method: "DELETE" }); setMsgs([]); } catch (e: any) { setErr(e.message); } };
  const addMem = async () => { try { await api("/api/agent/memory", { method: "POST", body: { text: newMem, kind: "preference" } }); setNewMem(""); loadMem(); loadStatus(); } catch (e: any) { setErr(e.message); } };
  const delMem = async (id: string) => { try { await api("/api/agent/memory/" + id, { method: "DELETE" }); loadMem(); loadStatus(); } catch (e: any) { setErr(e.message); } };

  const live = st?.mode === "agent";
  const banner = !st ? "" : live ? "" : !st.key_configured
    ? "מצב בסיסי: אני עונה מכללים מקומיים. להפעלת המוח החכם הוסף GEMINI_API_KEY בשרת והדלק את הדגל llm_extraction בפאנל הניהול."
    : "המפתח קיים. נשאר להדליק את הדגל llm_extraction בפאנל הניהול כדי שהסוכן החכם יעבוד.";

  return (
    <section className="card agent" aria-label="הסוכן">
      <header className="agent-head">
        <div><h3>הסוכן שלי</h3><p>שואל, מנתח, מבצע פעולות ומתאים את עצמו אליך.</p></div>
        <span className={"pill " + (live ? "on" : "off")}>{live ? `חכם · ${st.model}` : "בסיסי"}</span>
      </header>
      {banner && <div className="note">{banner}</div>}
      <div className="chat" role="log" aria-live="polite">
        {msgs.length === 0 && <div className="empty">עוד לא דיברנו. נסה אחת מהשאלות למטה, או כתוב משהו משלך.</div>}
        {msgs.map((m, i) => (
          <div key={i} className={"msg " + (m.role === "user" ? "me" : "bot")}>
            <div className="bubble">{m.content}</div>
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
