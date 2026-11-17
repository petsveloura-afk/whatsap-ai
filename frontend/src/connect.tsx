import { useEffect, useState } from "react";
import { Icon } from "./listings";
type Api = (path: string, o?: any) => Promise<any>;

/** Same pattern the server enforces (PUT /api/integrations/whatsapp/consent): optional +, 8 to 15 digits. */
export const validPhone = (v: string) => /^\+?\d{8,15}$/.test(v.replace(/[\s-]/g, ""));
export const cleanPhone = (v: string) => v.replace(/[\s-]/g, "");

/** Connections: WhatsApp notifications (explicit consent, official Cloud API) and Telegram as a listing source (link a chat or channel to a search).
 *  Uses endpoints that already existed in the backend but had no screen: /api/integrations/whatsapp/*, /api/integrations/telegram/sources. */
export function ConnectPanel({ api, searches, onChanged }: { api: Api; searches: any[]; onChanged?: () => void }) {
  const [wa, setWa] = useState<any>(null), [masked, setMasked] = useState<string | null>(null), [tg, setTg] = useState<any[]>([]);
  const [num, setNum] = useState(""), [agree, setAgree] = useState(false), [sid, setSid] = useState("");
  const [msg, setMsg] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false), [cmd, setCmd] = useState<{ cmd: string; note: string } | null>(null), [copied, setCopied] = useState(false);

  const load = async () => {
    try {
      const [w, t, p] = await Promise.all([api("/api/integrations/whatsapp/status"), api("/api/integrations/telegram/sources"), api("/api/profile").catch(() => null)]);
      setWa(w); setTg(t); setMasked(p?.contact?.whatsapp_masked || null);
    } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => { if (!sid && searches.length) setSid(searches[0].id); }, [searches]);

  const run = async (fn: () => Promise<any>) => { setBusy(true); setErr(""); setMsg(""); try { await fn(); await load(); onChanged?.(); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } };
  const saveWa = () => run(async () => { await api("/api/integrations/whatsapp/consent", { method: "PUT", body: { number: cleanPhone(num), consent: true } }); setNum(""); setAgree(false); setMsg("נשמר. התראות וואטסאפ מופעלות למספר שלך."); });
  const revokeWa = () => run(async () => { await api("/api/integrations/whatsapp/consent", { method: "DELETE" }); setMsg("ההסכמה בוטלה. לא יישלחו אליך הודעות בוואטסאפ."); });
  const addTg = () => run(async () => { const r = await api("/api/integrations/telegram/sources", { method: "POST", body: { search_id: sid } }); setCmd({ cmd: r.link_command, note: r.note }); setCopied(false); });
  const delTg = (id: string) => run(async () => { await api("/api/integrations/telegram/sources/" + id, { method: "DELETE" }); setMsg("החיבור הוסר."); });
  const copy = async () => { try { await navigator.clipboard.writeText(cmd!.cmd); setCopied(true); } catch { setCopied(false); } };
  const nameOf = (id: string) => searches.find(s => s.id === id)?.name || "חיפוש שנמחק";

  return <section className="pf-card" aria-label="חיבורים והתראות">
    <h3>חיבורים והתראות</h3>

    <div>
      <b><Icon n="chat" /> וואטסאפ</b>
      <p className="faint">התראות על הזדמנויות חדשות דרך WhatsApp Cloud API הרשמי, רק לאחר הסכמה מפורשת שלך.</p>
      {wa && !wa.configured && <div className="note">שליחת הודעות דורשת שהמנהל יגדיר את WhatsApp Cloud API בשרת. אפשר לשמור את ההסכמה כבר עכשיו.</div>}
      <div className="pf-row">
        <span className={"pill " + (wa?.consent ? "on" : "off")}>{wa?.consent ? "מופעל" : "כבוי"}</span>
        {masked && <span className="faint">מספר שמור: <bdi dir="ltr">{masked}</bdi></span>}
        {wa?.consent && <button type="button" className="ghost sm" onClick={revokeWa} disabled={busy}>בטל הסכמה</button>}
      </div>
      <div className="pf-row" style={{ marginTop: ".6rem" }}>
        <label htmlFor="cn-num" className="sr-only">מספר וואטסאפ</label>
        <input id="cn-num" type="tel" inputMode="tel" autoComplete="tel" dir="ltr" placeholder="+972501234567" value={num} onChange={e => setNum(e.target.value)} aria-invalid={num !== "" && !validPhone(num)} />
        <label className="pf-row"><input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} style={{ minHeight: 0 }} /> אני מאשר/ת לקבל התראות בוואטסאפ למספר הזה, ואפשר לבטל בכל רגע.</label>
        <button type="button" onClick={saveWa} disabled={busy || !agree || !validPhone(num)}>{wa?.consent ? "עדכן מספר" : "הפעל התראות"}</button>
      </div>
      {num !== "" && !validPhone(num) && <div className="faint" role="status">המספר צריך לכלול 8 עד 15 ספרות, עם קידומת מדינה (למשל 972).</div>}
    </div>

    <hr style={{ border: 0, borderTop: "1px solid var(--line)", width: "100%" }} />

    <div>
      <b><Icon n="send" /> טלגרם כמקור מודעות</b>
      <p className="faint">כל הודעה שתופיע בצ׳אט או בערוץ מקושר תנותח ותדורג עבור החיפוש שבחרת.</p>
      {searches.length === 0
        ? <div className="note">כדי לחבר טלגרם צריך קודם ליצור חיפוש.</div>
        : <div className="pf-row">
            <label htmlFor="cn-sid" className="sr-only">חיפוש לחיבור</label>
            <select id="cn-sid" value={sid} onChange={e => setSid(e.target.value)}>{searches.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
            <button type="button" onClick={addTg} disabled={busy || !sid}>צור קוד חיבור</button>
          </div>}
      {cmd && <div className="note" role="status">
        <ol style={{ margin: 0, paddingInlineStart: "1.2rem" }}>
          <li>הוסף את הבוט לצ׳אט או לערוץ.</li>
          <li>שלח שם את הפקודה: <code>{cmd.cmd}</code> <button type="button" className="ghost sm" onClick={copy}><Icon n="copy" /> {copied ? "הועתק" : "העתק"}</button></li>
          <li>אחרי שהבוט יאשר, הסטטוס כאן יתעדכן ל״מקושר״ (לחץ רענן).</li>
        </ol></div>}
      {tg.length > 0 && <ul className="pf-tips" style={{ marginTop: ".6rem" }}>{tg.map(t => <li key={t.id}>
        <span>{nameOf(t.search_id)}</span><span className={"pill " + (t.linked ? "on" : "off")}>{t.linked ? "מקושר" : "ממתין לקישור"}</span>
        <button type="button" className="ghost sm" onClick={() => delTg(t.id)} disabled={busy} aria-label={"הסר חיבור טלגרם של " + nameOf(t.search_id)}>הסר</button></li>)}</ul>}
      <div className="pf-row" style={{ marginTop: ".4rem" }}><button type="button" className="ghost sm" onClick={load} disabled={busy}>רענן</button></div>
    </div>

    <div aria-live="polite">{msg && <div className="ok">{msg}</div>}{err && <div className="err" role="alert">{err}</div>}</div>
  </section>;
}
