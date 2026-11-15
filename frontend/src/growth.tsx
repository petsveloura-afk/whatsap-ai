import { useEffect, useState, useCallback } from "react";
type Api = (path: string, o?: any) => Promise<any>;

/** Developer & growth tools: API keys, signed webhooks, referrals, weekly digest, market pool opt-in. All free. */
export function GrowthPanel({ api }: { api: Api }) {
  const [keys, setKeys] = useState<any[]>([]), [hooks, setHooks] = useState<any[]>([]), [ref, setRef] = useState<any>(null), [pool, setPool] = useState(false);
  const [shown, setShown] = useState(""), [hookUrl, setHookUrl] = useState(""), [code, setCode] = useState(""), [msg, setMsg] = useState(""), [digest, setDigest] = useState<any>(null);
  const load = useCallback(async () => {
    try { const [k, h, r, p] = await Promise.all([api("/api/keys"), api("/api/hooks"), api("/api/referrals/me"), api("/api/market/pool")]); setKeys(k); setHooks(h); setRef(r); setPool(p.enabled); } catch (e: any) { setMsg(e.message); }
  }, []);
  useEffect(() => { load(); }, []);
  const act = async (fn: () => Promise<any>, ok = "") => { try { setMsg(""); const r = await fn(); if (ok) setMsg(ok); await load(); return r; } catch (e: any) { setMsg(e.message); } };
  return <div className="card"><h3>כלים למפתחים וצמיחה</h3>
    <b>מפתחות API</b>
    {keys.map(k => <div key={k.id}>{k.name} · {k.prefix}… · {k.scopes.join(",")} {k.active ? "" : "(בוטל)"} {k.active && <button className="ghost" onClick={() => act(() => api(`/api/keys/${k.id}`, { method: "DELETE" }))}>בטל</button>}</div>)}
    <button onClick={() => act(async () => { const r = await api("/api/keys", { method: "POST", body: { name: "key " + (keys.length + 1), scopes: ["read", "ingest"] } }); setShown(r.key); })}>צור מפתח</button>
    {shown && <div className="ok">המפתח מוצג פעם אחת בלבד: <code>{shown}</code></div>}
    <hr /><b>Webhooks חתומים</b>
    {hooks.map(h => <div key={h.id}>{h.url} · כשלונות: {h.fail_count} {h.active ? "" : "(מושבת)"} <button className="ghost" onClick={() => act(() => api(`/api/hooks/${h.id}/test`, { method: "POST" }), "נשלחה בדיקה")}>בדיקה</button> <button className="ghost" onClick={() => act(() => api(`/api/hooks/${h.id}`, { method: "DELETE" }))}>מחק</button></div>)}
    <input dir="ltr" placeholder="https://..." value={hookUrl} onChange={e => setHookUrl(e.target.value)} />
    <button onClick={() => act(async () => { const r = await api("/api/hooks", { method: "POST", body: { url: hookUrl } }); setHookUrl(""); setShown(r.secret); })}>הוסף webhook</button>
    <hr /><b>הפניות</b>
    {ref && <div>הקוד שלך: <code>{ref.code}</code> · הופנו: {ref.referred} · בונוס מכסת API יומית: +{ref.bonus_daily_api_requests}</div>}
    <input dir="ltr" placeholder="קוד הפניה של חבר" maxLength={8} value={code} onChange={e => setCode(e.target.value.toUpperCase())} />
    <button className="ghost" onClick={() => act(() => api("/api/referrals/claim", { method: "POST", body: { code } }), "הקוד נקלט")}>הפעל קוד</button>
    <hr /><b>פרטיות ושיפור השוק</b>
    <label><input type="checkbox" checked={pool} onChange={e => act(() => api("/api/market/pool", { method: "PUT", body: { enabled: e.target.checked } }))} /> שתף נקודות מחיר אנונימיות (קטגוריה, אזור, חדרים, מחיר - בלי טקסט ובלי זהות) כדי לשפר השוואות שוק</label>
    <div><button className="ghost" onClick={() => act(() => api("/api/digest/subscribe", { method: "PUT", body: { enabled: true } }), "דיגסט שבועי הופעל")}>הפעל דיגסט שבועי</button> <button className="ghost" onClick={() => act(async () => setDigest(await api("/api/digest/preview")))}>תצוגה מקדימה</button></div>
    {digest && <pre style={{ whiteSpace: "pre-wrap" }}>{digest.subject + "\n\n" + digest.body}</pre>}
    <div className="err">{msg}</div></div>;
}
