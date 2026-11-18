import { useEffect, useState } from "react";

type Api = (path: string, o?: any) => Promise<any>;

/** v3.17: handles the link from the verification e-mail (?verify=TOKEN). Works logged-in or logged-out. */
export function VerifyLinkHandler({ api }: { api: Api }) {
  const [res, setRes] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    const t = new URLSearchParams(location.search).get("verify");
    if (!t) return;
    try { history.replaceState(null, "", location.pathname + location.hash); } catch {}   // the token never stays in the address bar / history
    api("/api/auth/verify-email", { method: "POST", body: { token: t } })
      .then(() => { setRes({ ok: true, text: "כתובת האימייל אומתה בהצלחה ✓" }); window.dispatchEvent(new Event("email-verified")); })
      .catch((e: any) => setRes({ ok: false, text: e?.message || "קישור האימות אינו תקף או שפג תוקפו." }));
  }, []);
  useEffect(() => { if (!res) return; const id = setTimeout(() => setRes(null), 9000); return () => clearTimeout(id); }, [res]);
  if (!res) return null;
  return <div className={"verify-toast " + (res.ok ? "ok" : "bad")} role="status" onClick={() => setRes(null)}>{res.text}</div>;
}

/** v3.17: shown inside the dashboard until the e-mail is confirmed. Self-contained: no props to thread through the app. */
export function VerifyBanner({ api, user, flash }: { api: Api; user: any; flash: (m: string) => void }) {
  const [me, setMe] = useState<any>(user), [wait, setWait] = useState(0), [busy, setBusy] = useState(false);
  const refresh = () => api("/api/auth/me").then(setMe).catch(() => {});
  useEffect(() => { window.addEventListener("email-verified", refresh); return () => window.removeEventListener("email-verified", refresh); }, []);
  useEffect(() => { if (wait <= 0) return; const id = setTimeout(() => setWait(wait - 1), 1000); return () => clearTimeout(id); }, [wait]);
  if (!me || me.email_verified !== false || !me.verification_required) return null;
  const resend = async () => {
    setBusy(true);
    try { await api("/api/auth/resend-verification", { method: "POST" }); flash("שלחנו קישור אימות חדש למייל"); setWait(60); }
    catch (e: any) { flash(e?.message || "לא הצלחנו לשלוח. נסו שוב בעוד רגע."); }
    finally { setBusy(false); }
  };
  return <div className="verify-banner" role="status">
    <div><b>אמתו את כתובת האימייל</b><span>שלחנו קישור אל {me.email}. האימות נדרש לפני תשלום, כדי שהקבלה תגיע אליכם.</span></div>
    <div className="verify-act"><button disabled={busy || wait > 0} onClick={resend}>{wait > 0 ? `שליחה חוזרת בעוד ${wait} ש׳` : "שלחו לי שוב"}</button><button className="ghost" onClick={refresh}>כבר אימתתי</button></div>
  </div>;
}

/** Full-screen gate: an unverified account sees only this until the e-mail is confirmed (the API refuses everything else with 403). */
export function VerifyGate({ api, user, onUser, onLogout }: { api: Api; user: any; onUser: (u: any) => void; onLogout: () => void }) {
  const [wait, setWait] = useState(0), [busy, setBusy] = useState(false), [note, setNote] = useState("");
  const refresh = () => api("/api/auth/me").then((m: any) => { if (m.email_verified !== false) onUser(m); else setNote("האימייל עדיין לא אומת. פתחו את הקישור שנשלח אליכם."); }).catch(() => {});
  useEffect(() => { window.addEventListener("email-verified", refresh); return () => window.removeEventListener("email-verified", refresh); }, []);
  useEffect(() => { if (wait <= 0) return; const id = setTimeout(() => setWait(wait - 1), 1000); return () => clearTimeout(id); }, [wait]);
  const resend = async () => {
    setBusy(true);
    try { await api("/api/auth/resend-verification", { method: "POST" }); setNote("שלחנו קישור חדש. בדקו גם בתיקיית הספאם."); setWait(60); }
    catch (e: any) { setNote(e?.message || "לא הצלחנו לשלוח. נסו שוב בעוד רגע."); }
    finally { setBusy(false); }
  };
  return <div className="wrap card" style={{ maxWidth: 520, margin: "10vh auto", textAlign: "center" }} role="status">
    <h2>אמתו את כתובת האימייל</h2>
    <p>שלחנו קישור אימות אל <b dir="ltr">{user.email}</b>. אחרי הלחיצה על הקישור תיכנסו למערכת.</p>
    {note && <p className="hint warn">{note}</p>}
    <div className="verify-act" style={{ justifyContent: "center" }}>
      <button disabled={busy || wait > 0} onClick={resend}>{wait > 0 ? `שליחה חוזרת בעוד ${wait} ש׳` : "שלחו לי שוב"}</button>
      <button className="ghost" onClick={refresh}>כבר אימתתי</button>
      <button className="ghost" onClick={onLogout}>יציאה</button>
    </div>
  </div>;
}
