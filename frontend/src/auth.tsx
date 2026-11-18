import { useEffect, useState } from "react";
import { emailProblem, passwordIssues, passwordStrength, strengthLabel } from "./lib/auth";
type Props = { api: (path: string, o?: any) => Promise<any>; login: (email: string, pw: string) => Promise<any>; onAuth: (u: any) => void };
/** Sign-in / sign-up card: tabs, live password rules + strength, show/hide, confirmation, terms, hidden bot trap, caps-lock hint, clear errors. */
export function AuthCard({ api, login, onAuth }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login"), [email, setEmail] = useState(""), [pw, setPw] = useState(""), [pw2, setPw2] = useState("");
  const [show, setShow] = useState(false), [terms, setTerms] = useState(false), [trap, setTrap] = useState(""), [msg, setMsg] = useState(""), [info, setInfo] = useState(""), [busy, setBusy] = useState(false), [caps, setCaps] = useState(false), [touched, setTouched] = useState(false);
  const reg = mode === "register", issues = reg ? passwordIssues(pw, email) : [], strength = passwordStrength(pw), sl = strengthLabel(strength);
  useEffect(() => { setMsg(""); setInfo(""); }, [mode]);
  const validate = (): string => {
    const e = emailProblem(email); if (e) return e;
    if (!pw) return "נא להזין סיסמה";
    if (reg) { if (issues.length) return "הסיסמה צריכה: " + issues.join(" · "); if (pw !== pw2) return "אימות הסיסמה אינו תואם"; if (!terms) return "יש לאשר את תנאי השימוש ומדיניות הפרטיות"; }
    return "";
  };
  const submit = async () => {
    setTouched(true); const bad = validate(); if (bad) { setMsg(bad); return; }
    setBusy(true); setMsg(""); setInfo("");
    try {
      if (reg) await api("/api/auth/register", { method: "POST", body: { email: email.trim(), password: pw, website: trap, accept_terms: true } });
      onAuth(await login(email.trim(), pw));
    } catch (e: any) { setMsg(e.message || "משהו השתבש"); } finally { setBusy(false); }
  };
  const forgot = async () => {
    const e = emailProblem(email); if (e) { setMsg("הזינו את כתובת האימייל כדי לקבל קישור איפוס"); return; }
    setBusy(true); setMsg("");
    try { await api("/api/auth/forgot-password", { method: "POST", body: { email: email.trim() } }); setInfo("אם החשבון קיים, נשלח אליו מייל איפוס"); } catch (x: any) { setMsg(x.message); } finally { setBusy(false); }
  };
  const caps_ = (e: React.KeyboardEvent) => setCaps(e.getModifierState?.("CapsLock") ?? false);
  return <form className="card auth auth-v10" onSubmit={e => { e.preventDefault(); submit(); }} noValidate aria-busy={busy}>
    <div className="auth-tabs" role="tablist"><button type="button" role="tab" aria-selected={!reg} className={!reg ? "on" : ""} onClick={() => setMode("login")}>כניסה</button><button type="button" role="tab" aria-selected={reg} className={reg ? "on" : ""} onClick={() => setMode("register")}>הרשמה</button></div>
    <h3>{reg ? "יוצרים חשבון חדש" : "ברוכים השבים"}</h3>
    <label className="fld"><span>אימייל</span><input type="email" dir="ltr" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false} placeholder="name@example.com" value={email} onChange={e => setEmail(e.target.value)} aria-invalid={touched && !!emailProblem(email)} /></label>
    <label className="fld"><span>סיסמה</span><div className="pwrow"><input type={show ? "text" : "password"} dir="ltr" autoComplete={reg ? "new-password" : "current-password"} placeholder={reg ? "לפחות 10 תווים" : "הסיסמה שלך"} value={pw} onChange={e => setPw(e.target.value)} onKeyUp={caps_} onKeyDown={caps_} /><button type="button" className="ghost sm eye" onClick={() => setShow(!show)} aria-label={show ? "הסתר סיסמה" : "הצג סיסמה"}>{show ? "הסתר" : "הצג"}</button></div></label>
    {caps && <div className="hint warn">Caps Lock פעיל</div>}
    {reg && <>
      <div className={"meter l" + sl.level} aria-hidden="true"><i style={{ inlineSize: strength + "%" }} /></div>
      <div className="hint">{pw ? <>חוזק: <b>{sl.text}</b></> : "בחרו סיסמה ייחודית שלא משתמשים בה באתרים אחרים"}</div>
      {pw && issues.length > 0 && <ul className="rules">{issues.map(i => <li key={i}>✗ {i}</li>)}</ul>}
      <label className="fld"><span>אימות סיסמה</span><input type={show ? "text" : "password"} dir="ltr" autoComplete="new-password" value={pw2} onChange={e => setPw2(e.target.value)} aria-invalid={!!pw2 && pw !== pw2} />{pw2 && pw !== pw2 && <small className="err">הסיסמאות אינן זהות</small>}</label>
      <label className="check"><input type="checkbox" checked={terms} onChange={e => setTerms(e.target.checked)} /><span>אני מאשר/ת את תנאי השימוש ומדיניות הפרטיות</span></label>
      <div className="hp" aria-hidden="true"><label>אתר<input tabIndex={-1} autoComplete="off" value={trap} onChange={e => setTrap(e.target.value)} /></label></div>
    </>}
    <button type="submit" disabled={busy}>{busy ? "רגע..." : reg ? "מתחילים למצוא הזדמנויות" : "כניסה"}</button>
    <button type="button" className="ghost" onClick={() => setMode(reg ? "login" : "register")}>{reg ? "יש חשבון? כניסה" : "אין חשבון? הרשמה"}</button>
    {!reg && <button type="button" className="ghost" onClick={forgot} disabled={busy}>שכחתי סיסמה</button>}
    <div className="err" role="alert">{msg}</div>{info && <div className="ok" role="status">{info}</div>}
    <p className="faint secnote">🔒 החיבור מוצפן. סיסמאות נשמרות מוצפנות בלבד, והחשבון ננעל זמנית אחרי ניסיונות כושלים חוזרים.</p>
  </form>;
}
