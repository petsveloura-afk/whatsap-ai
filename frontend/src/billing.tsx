import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./listings";
import "./styles.billing.css";

type Api = (path: string, o?: any) => Promise<any>;

/** v3.15 payments UI.
 *  - Card: PayPal "Card Fields". The card number / expiry / CVV are typed into iframes hosted by PayPal, so the payer does NOT need a
 *    PayPal account or login and the card data never reaches this app or our server (only an order id does).
 *  - PayPal: the standard PayPal button (+ PayPal's own guest card button when Card Fields are not enabled on the business account).
 *  - The amount is decided by the server; the browser only says which plan and period.
 *  - Access is granted only after the server captured and verified the payment. */
const PLAN_HE: any = { starter: "Starter", pro: "Pro", vip: "VIP" };
const PERIOD_HE: any = { monthly: "חודשי", yearly: "שנתי" };
const STATUS_HE: any = { completed: "שולם", refunded: "זוכה", pending: "ממתין לאישור", failed: "נכשל", created: "נפתח" };
const nf = new Intl.NumberFormat("he-IL", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const money = (a: any, cur = "ILS") => nf.format(Number(a)) + (cur === "ILS" ? " ₪" : " " + cur);
function toDate(s?: string | null): Date | null {
  if (!s) return null;
  let t = String(s).replace(" ", "T"); if (!/(Z|[+-]\d\d:?\d\d)$/.test(t)) t += "Z";   // the API sends UTC; SQLite omits the offset
  const d = new Date(t); return isNaN(d.getTime()) ? null : d;
}
const dateHe = (s?: string | null) => { const d = toDate(s); return d ? d.toLocaleDateString("he-IL") : ""; };
const hebrewOr = (e: any, fallback: string) => (typeof e?.message === "string" && /[\u0590-\u05FF]/.test(e.message) ? e.message : fallback);

let sdkPromise: Promise<any> | null = null, sdkKey = "";
/** Loads PayPal's JS SDK once, only when the payer opens the payment step (no third-party script on normal page views). */
function loadSdk(clientId: string, currency: string): Promise<any> {
  const key = clientId + "|" + currency;
  if (sdkPromise && sdkKey === key) return sdkPromise;
  sdkKey = key;
  sdkPromise = new Promise((resolve, reject) => {
    const w = window as any, s = document.createElement("script");
    s.src = "https://www.paypal.com/sdk/js?client-id=" + encodeURIComponent(clientId) + "&components=buttons,card-fields&enable-funding=card&disable-funding=paylater,venmo,credit&currency=" + encodeURIComponent(currency) + "&intent=capture&locale=he_IL";
    s.async = true;
    s.onload = () => (w.paypal ? resolve(w.paypal) : reject(new Error("paypal sdk missing")));
    s.onerror = () => { sdkPromise = null; reject(new Error("paypal sdk blocked")); };
    document.head.appendChild(s);
  });
  return sdkPromise;
}

function PayBox({ api, cfg, plan, period, amount, onCaptured }: any) {
  const [sdk, setSdk] = useState("loading"), [method, setMethod] = useState("paypal"), [inline, setInline] = useState(false);
  const [cardOk, setCardOk] = useState(true), [busy, setBusy] = useState(false), [err, setErr] = useState(""), [retry, setRetry] = useState("");
  const cf = useRef<any>(null);
  const capture = useCallback(async (orderId: string) => {
    setBusy(true); setErr(""); setRetry("");
    try { onCaptured(await api(`/api/billing/order/${encodeURIComponent(orderId)}/capture`, { method: "POST" })); }
    catch (e: any) { setErr(hebrewOr(e, "לא הצלחנו להשלים את התשלום. אם חויבתם, החבילה תופעל אוטומטית.")); if (String(e?.message).includes("אל תשלמו שוב")) setRetry(orderId); }
    finally { setBusy(false); }
  }, [api, onCaptured]);
  const capRef = useRef(capture); capRef.current = capture;   // the PayPal widgets keep the first callbacks they get; always call the latest

  useEffect(() => {
    let off = false;
    loadSdk(cfg.paypal.client_id, cfg.currency).then((pp: any) => {
      if (off) return;
      // the inline card form is offered ONLY when the PayPal business account really supports it; otherwise it stays hidden
      try { setInline(!!cfg.cards && !!pp.CardFields({ createOrder: () => "", onApprove: () => {} }).isEligible()); } catch { setInline(false); }
      setSdk("ready");
    }).catch(() => { if (!off) setSdk("error"); });
    return () => { off = true; };
  }, []);

  useEffect(() => {
    if (sdk !== "ready") return;
    const pp = (window as any).paypal; let alive = true; const undo: (() => void)[] = [];
    const order = (m: string) => async () => { setErr(""); const r = await api("/api/billing/order", { method: "POST", body: { plan, period, method: m } }); return r.order_id; };
    const fail = (e: any) => { if (alive) { setErr(hebrewOr(e, "אירעה שגיאה בתשלום. לא חויבתם. אפשר לנסות שוב.")); setBusy(false); } };
    const approve = (d: any) => capRef.current(d.orderID);
    try {
      if (method === "card") {
        const inst = pp.CardFields({
          createOrder: order("card"), onApprove: approve, onError: fail,
          style: { input: { "font-size": "16px", "font-family": "Heebo, Arial, sans-serif", color: "#111827" }, ".invalid": { color: "#b91c1c" } },
        });
        if (!inst.isEligible()) { setCardOk(false); return; }
        setCardOk(true);
        inst.NameField({ placeholder: "שם על הכרטיס" }).render("#pp-name");
        inst.NumberField({ placeholder: "מספר כרטיס" }).render("#pp-number");
        inst.ExpiryField({ placeholder: "MM/YY" }).render("#pp-expiry");
        inst.CVVField({ placeholder: "CVV" }).render("#pp-cvv");
        cf.current = inst; undo.push(() => { cf.current = null; try { inst.close && inst.close(); } catch {} });
      } else {
        const common = { createOrder: order("paypal"), onApprove: approve, onError: fail, onCancel: () => { if (alive) { setErr("התשלום בוטל. לא חויבתם."); setBusy(false); } } };
        const b = pp.Buttons({ ...common, fundingSource: pp.FUNDING ? pp.FUNDING.PAYPAL : undefined, style: { layout: "vertical", shape: "pill", label: "pay", height: 48 } });
        if (b.isEligible()) { b.render("#pp-buttons"); undo.push(() => { try { b.close(); } catch {} }); }
        if (pp.FUNDING && pp.FUNDING.CARD) {   // PayPal-hosted guest card form: also no PayPal login needed
          const g = pp.Buttons({ ...common, fundingSource: pp.FUNDING.CARD, style: { layout: "vertical", shape: "pill", color: "black", label: "pay", height: 48 } });
          if (g.isEligible()) { g.render("#pp-guest"); undo.push(() => { try { g.close(); } catch {} }); }
        }
      }
    } catch (e) { fail(e); }
    return () => { alive = false; undo.forEach(f => f()); };
  }, [sdk, method, plan, period]);

  const submit = async () => {
    if (!cf.current || busy) return;
    setErr(""); setBusy(true);
    try { await cf.current.submit(); }   // validates the fields, runs 3-D Secure if the bank asks, then PayPal calls onApprove
    catch { setErr("בדקו את פרטי הכרטיס ונסו שוב."); setBusy(false); }
  };

  return <div className="pay-box">
    <div className="pay-tabs" role="tablist" aria-label="אמצעי תשלום">
      {inline && <>
        <button role="tab" aria-selected={method === "paypal"} className={"ghost" + (method === "paypal" ? " on" : "")} onClick={() => { setErr(""); setMethod("paypal"); }}>PayPal / כרטיס</button>
        <button role="tab" aria-selected={method === "card"} className={"ghost" + (method === "card" ? " on" : "")} onClick={() => { setErr(""); setMethod("card"); }}>הזנת כרטיס כאן</button>
      </>}
    </div>
    {sdk === "loading" && <p className="faint" role="status">טוען טופס תשלום מאובטח…</p>}
    {sdk === "error" && <p className="err" role="alert">לא הצלחנו לטעון את שירות התשלום של PayPal. בדקו חיבור לרשת / חוסם פרסומות ורעננו את הדף.</p>}
    {sdk === "ready" && method === "card" && inline && <div className="pay-card">
        <span className="pp-lbl">שם על הכרטיס</span><div id="pp-name" className="pp-field" />
        <span className="pp-lbl">מספר כרטיס</span><div id="pp-number" className="pp-field" />
        <div className="pp-row"><div><span className="pp-lbl">תוקף</span><div id="pp-expiry" className="pp-field" /></div><div><span className="pp-lbl">קוד אבטחה (CVV)</span><div id="pp-cvv" className="pp-field" /></div></div>
        <button disabled={busy} onClick={submit}>{busy ? "מעבד תשלום…" : `שלם ${money(amount, cfg.currency)}`}</button>
      </div>}
    {sdk === "ready" && method === "paypal" && <div className={"pay-methods" + (busy ? " pay-wait" : "")}>
      <span className="pay-lbl">בחרו אמצעי תשלום · {money(amount, cfg.currency)}</span>
      <div id="pp-buttons" />
      <div className="pay-or" aria-hidden="true"><span>או</span></div>
      <span className="pay-lbl">תשלום בכרטיס אשראי / דביט, בלי חשבון PayPal</span>
      <div id="pp-guest" />
    </div>}
    {busy && <p className="faint" role="status">מאמתים את התשלום…</p>}
    {err && <div className="err" role="alert">{err}</div>}
    {retry && <button className="ghost" disabled={busy} onClick={() => capRef.current(retry)}>בדיקת מצב התשלום</button>}
    <p className="faint pay-trust"><Icon n="shield" /> פרטי הכרטיס מוזנים בשדות המאובטחים של PayPal ואינם עוברים דרך השרתים שלנו. החבילה מופעלת רק אחרי אישור התשלום.</p>
  </div>;
}

function ReceiptModal({ html, onClose }: { html: string; onClose: () => void }) {
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k); }, []);
  // sandbox WITHOUT allow-same-origin: the receipt runs in an opaque origin and can never touch this app's tokens/storage, even in theory
  return <div className="modal" role="dialog" aria-modal="true" aria-label="קבלה" onClick={onClose}>
    <div className="modal-box" onClick={e => e.stopPropagation()}><button className="ghost sm" onClick={onClose}>סגור</button><iframe title="קבלה" sandbox="allow-modals" srcDoc={html} /></div>
  </div>;
}

export function BillingPanel({ api, sub, onChanged, flash, onNavigate }: any) {
  const [cfg, setCfg] = useState<any>(null), [plan, setPlan] = useState("pro"), [period, setPeriod] = useState("monthly"), [step, setStep] = useState("choose");
  const [result, setResult] = useState<any>(null), [hist, setHist] = useState<any[]>([]), [msg, setMsg] = useState(""), [receipt, setReceipt] = useState("");
  const loadHist = useCallback(async () => { try { setHist((await api("/api/billing/payments")).items || []); } catch {} }, [api]);
  useEffect(() => { api("/api/billing/config").then(setCfg).catch((e: any) => setMsg(e.message)); loadHist(); }, []);

  // coming back from PayPal's approval page of the recurring subscription (?billing=return|cancel)
  useEffect(() => {
    const b = new URLSearchParams(location.search).get("billing"); if (!b) return;
    try { history.replaceState(null, "", location.pathname + location.hash); } catch {}
    if (onNavigate) onNavigate();
    if (b === "cancel") { flash("הפעולה בוטלה. לא חויבתם."); return; }
    flash("האישור התקבל מ-PayPal. מפעילים את החבילה…");
    let n = 0; const t = setInterval(() => { onChanged(); loadHist(); if (++n >= 6) clearInterval(t); }, 4000);
    return () => clearInterval(t);
  }, []);

  const captured = useCallback((r: any) => { setResult(r); setStep("done"); onChanged(); loadHist(); }, [onChanged, loadHist]);
  const openReceipt = async (id: string) => { try { setReceipt((await api(`/api/billing/receipt/${id}`)).html); } catch (e: any) { flash(e.message); } };
  const mailReceipt = async (id: string) => { try { await api(`/api/billing/receipt/${id}/email`, { method: "POST" }); flash("הקבלה נשלחה למייל שלך"); } catch (e: any) { flash(e.message); } };
  const recurring = async (p: string) => {
    if (!confirm("מנוי מתחדש: PayPal יחייב אותך אוטומטית כל חודש עד שתבטל. להמשיך?")) return;
    try { const r = await api("/api/billing/checkout", { method: "POST", body: { plan: p } }); location.href = r.approve_url; } catch (e: any) { setMsg(e.message); }
  };
  const cancelRecurring = async () => {
    if (!confirm("לבטל את המנוי המתחדש? הביטול יאושר על ידי PayPal ובדרך כלל נכנס לתוקף מיד.")) return;
    try { await api("/api/billing/cancel", { method: "POST" }); flash("בקשת הביטול נשלחה"); setTimeout(onChanged, 3000); } catch (e: any) { setMsg(e.message); }
  };

  if (!cfg) return <div className="card"><h3>מנוי ותשלום</h3><p className="faint">{msg || "טוען…"}</p></div>;
  const chosen = cfg.plans.find((p: any) => p.id === plan) || cfg.plans[0];
  const amount = chosen ? chosen[period] : "0";
  const end = toDate(sub.period_end), daysLeft = end ? Math.ceil((end.getTime() - Date.now()) / 86400000) : null;
  const paid = sub.plan && sub.plan !== "starter";
  const blocked = (p: string) => (paid && !sub.recurring && sub.plan !== p) || sub.recurring;

  return <div className="card billing">
    <h3>מנוי ותשלום</h3>
    {paid && <div className={"sub-now" + (daysLeft !== null && daysLeft <= 3 ? " warn" : "")}>
      <b>החבילה שלך: {PLAN_HE[sub.plan] || sub.plan}</b>
      <span>{sub.recurring ? "מתחדשת אוטומטית דרך PayPal" : `פעילה עד ${dateHe(sub.period_end)}${daysLeft !== null ? ` (${daysLeft > 0 ? `עוד ${daysLeft} ימים` : "מסתיימת היום"})` : ""}`}</span>
      {sub.recurring && <button className="danger sm" onClick={cancelRecurring}>ביטול מנוי מתחדש</button>}
    </div>}
    {!paid && sub.expired && <div className="sub-now warn"><b>החבילה הקודמת הסתיימה</b><span>אפשר לחדש בכל רגע ולחזור למלוא היכולות.</span></div>}
    {msg && <div className="err" role="alert">{msg}</div>}

    {!cfg.available && <p className="faint">התשלום אינו זמין כרגע. אם הבעיה נמשכת פנו אלינו.</p>}

    {cfg.available && step === "choose" && <>
      <div className="pay-tabs" role="radiogroup" aria-label="תקופת חיוב">
        {["monthly", "yearly"].map(k => <button key={k} role="radio" aria-checked={period === k} className={"ghost" + (period === k ? " on" : "")} onClick={() => setPeriod(k)}>{PERIOD_HE[k]}{k === "yearly" && chosen && Number(chosen.yearly_saving) > 0 ? ` · חוסכים ${money(chosen.yearly_saving, cfg.currency)}` : ""}</button>)}
      </div>
      <div className="plans">{cfg.plans.map((p: any) => <div className={"plan-card" + (p.id === "pro" ? " hot" : "")} key={p.id}>
        <b>{p.name}</b><span className="pr">{money(p[period], cfg.currency)}</span>
        <span className="faint">{period === "monthly" ? "לחודש" : `לשנה (${p.yearly_months} חודשי תשלום)`} · עד {p.max_searches} חיפושים פעילים</span>
        <button disabled={blocked(p.id)} onClick={() => { setPlan(p.id); setStep("pay"); setResult(null); }}>{sub.plan === p.id && !sub.recurring ? "חידוש" : "לתשלום"} · {p.name}</button>
        {period === "monthly" && cfg.subscriptions_available && !paid && <button className="ghost sm" onClick={() => recurring(p.id)}>או מנוי חודשי מתחדש (PayPal)</button>}
      </div>)}</div>
      {paid && !sub.recurring && <p className="faint">חידוש לפני הסיום מוסיף את התקופה החדשה אחרי התקופה הנוכחית, בלי לאבד ימים ששולמו. מעבר בין חבילות אפשר בסיום התקופה.</p>}
      <p className="faint">חיוב בשקלים. תשלום בכרטיס אשראי בלי צורך בחשבון PayPal. קבלה נשלחת למייל ונשמרת באזור החשבון.</p>
    </>}

    {cfg.available && step === "pay" && chosen && <>
      <div className="pay-sum"><div><b>{chosen.name} · {PERIOD_HE[period]}</b><span className="faint">{money(amount, cfg.currency)} · ללא חידוש אוטומטי</span></div><button className="ghost sm" onClick={() => setStep("choose")}>שינוי חבילה</button></div>
      <PayBox key={plan + period} api={api} cfg={cfg} plan={plan} period={period} amount={amount} onCaptured={captured} />
    </>}

    {step === "done" && result && (result.status === "completed"
      ? <div className="pay-done" role="status"><h4>התשלום התקבל, תודה! ✓</h4>
        <p>חבילת <b>{PLAN_HE[result.plan] || result.plan}</b> פעילה{result.access_until ? ` עד ${dateHe(result.access_until)}` : ""}. מספר קבלה: <b className="mono">{result.payment?.receipt_no}</b></p>
        <div className="rowf"><button onClick={() => openReceipt(result.payment.id)}>הצג / הדפס קבלה</button><button className="ghost" onClick={() => mailReceipt(result.payment.id)}>שלח למייל</button><button className="ghost" onClick={() => setStep("choose")}>סגור</button></div></div>
      : <div className="pay-done" role="status"><h4>התשלום התקבל וממתין לאישור סופי</h4><p>{result.message}</p><button className="ghost" onClick={() => { setStep("choose"); onChanged(); }}>סגור</button></div>)}

    {hist.length > 0 && <><h4 className="pay-h">היסטוריית תשלומים</h4>
      <div className="tbl-wrap"><table className="pay-tbl"><thead><tr><th>תאריך</th><th>קבלה</th><th>חבילה</th><th>סכום</th><th>אמצעי</th><th>סטטוס</th><th /></tr></thead><tbody>{hist.map(h => <tr key={h.id}>
        <td>{dateHe(h.paid_at)}</td><td className="mono">{h.receipt_no || "-"}</td><td>{PLAN_HE[h.plan] || h.plan}{h.period ? ` · ${PERIOD_HE[h.period] || h.period}` : ""}</td><td>{money(h.amount, h.currency)}</td>
        <td>{h.method === "card" ? `כרטיס${h.card_last4 ? " ••••" + h.card_last4 : ""}` : h.method === "subscription" ? "מנוי PayPal" : "PayPal"}</td>
        <td><span className={"status " + (h.status === "completed" ? "saved" : h.status === "refunded" ? "rejected" : "")}>{STATUS_HE[h.status] || h.status}</span></td>
        <td>{h.receipt_no && <><button className="ghost sm" onClick={() => openReceipt(h.id)}>קבלה</button> <button className="ghost sm" onClick={() => mailReceipt(h.id)}>במייל</button></>}</td></tr>)}</tbody></table></div></>}
    {receipt && <ReceiptModal html={receipt} onClose={() => setReceipt("")} />}
  </div>;
}

/** Admin: revenue, every payment attempt and a one-click full refund (server re-checks the role and the payment state). */
export function BillingAdmin({ api, flash }: any) {
  const [d, setD] = useState<any>(null), [f, setF] = useState(""), [msg, setMsg] = useState("");
  const load = useCallback(async () => { try { setMsg(""); setD(await api("/api/admin/billing/payments" + (f ? "?status=" + f : ""))); } catch (e: any) { setMsg(e.message); } }, [api, f]);
  useEffect(() => { load(); }, [f]);
  const refund = async (p: any) => {
    if (!confirm(`לזכות את התשלום ${p.receipt_no} על ${money(p.amount, p.currency)}? הכסף יוחזר ללקוח והחבילה שנרכשה תוסר.`)) return;
    try { await api(`/api/admin/billing/payments/${p.id}/refund`, { method: "POST", body: {} }); flash("התשלום זוכה"); load(); } catch (e: any) { setMsg(e.message); }
  };
  return <div className="card"><h3>תשלומים וקבלות</h3>
    {msg && <div className="err" role="alert">{msg}</div>}
    {d && <><p className="faint">סה״כ הכנסות ששולמו: <b>{money(d.revenue_total, d.currency)}</b> · {Object.entries(d.counts || {}).map(([k, v]: any) => `${STATUS_HE[k] || k}: ${v}`).join(" · ")}</p>
      <div className="pay-tabs">{["", "completed", "pending", "failed", "refunded"].map(k => <button key={k} className={"ghost sm" + (f === k ? " on" : "")} onClick={() => setF(k)}>{k ? STATUS_HE[k] : "הכל"}</button>)}</div>
      <div className="tbl-wrap"><table className="pay-tbl"><tbody>{d.items.map((p: any) => <tr key={p.id}>
        <td>{dateHe(p.paid_at || p.created_at)}</td><td>{p.customer_email}</td><td className="mono">{p.receipt_no || "-"}</td><td>{PLAN_HE[p.plan]} · {PERIOD_HE[p.period]}</td><td>{money(p.amount, p.currency)}</td>
        <td><span className={"status " + (p.status === "completed" ? "saved" : p.status === "failed" || p.status === "refunded" ? "rejected" : "")} title={p.failure_reason || ""}>{STATUS_HE[p.status] || p.status}</span></td>
        <td>{p.status === "completed" && p.method !== "subscription" && <button className="danger sm" onClick={() => refund(p)}>זיכוי</button>}</td></tr>)}</tbody></table></div></>}
  </div>;
}
