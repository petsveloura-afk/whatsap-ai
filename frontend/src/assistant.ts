import { createElement as h, useState } from "react";
type Api = (path: string, o?: any) => Promise<any>;

/** v3.2: free assistant over your own listings + one-click source discovery + search report. Uses only the new /api/assistant,
 *  /api/sources/suggest(/apply) and /api/searches/{id}/report endpoints. Written without JSX so it never conflicts with existing panels. */
export function AssistantPanel({ api, searches }: { api: Api; searches: any[] }) {
  const [q, setQ] = useState(""), [sid, setSid] = useState(""), [ans, setAns] = useState<any>(null), [sug, setSug] = useState<any>(null);
  const [rep, setRep] = useState<any>(null), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<void>) => { try { setMsg(""); setBusy(true); await fn(); } catch (e: any) { setMsg(e.message); } finally { setBusy(false); } };
  const ask = () => run(async () => { setAns(await api("/api/assistant", { method: "POST", body: { question: q, search_id: sid || null } })); });
  const discover = () => run(async () => { setSug(await api("/api/sources/suggest?search_id=" + encodeURIComponent(sid))); });
  const apply = () => run(async () => { const r = await api("/api/sources/suggest/apply", { method: "POST", body: { search_id: sid } }); setMsg("נוספו " + r.added.length + " מקורות" + (r.skipped.length ? " · דולגו " + r.skipped.length : "")); });
  const report = () => run(async () => { setRep(await api("/api/searches/" + sid + "/report")); });
  const needSearch = !sid;
  return h("div", { className: "card" },
    h("h3", null, "עוזר חכם"),
    h("p", null, "שאל על ההזדמנויות שלך: מה הכי זול? מה הכי מתאים בחולון? למה נפסלו מודעות? יש סימני אזהרה? תן סיכום."),
    h("select", { value: sid, onChange: (e: any) => setSid(e.target.value) }, h("option", { value: "" }, "כל החיפושים"), ...searches.map(s => h("option", { key: s.id, value: s.id }, s.name))),
    h("input", { placeholder: "מה תרצה לדעת?", value: q, onChange: (e: any) => setQ(e.target.value), onKeyDown: (e: any) => { if (e.key === "Enter" && q.length > 1) ask(); } }),
    h("button", { onClick: ask, disabled: busy || q.trim().length < 2 }, "שאל"),
    h("button", { className: "ghost", onClick: discover, disabled: busy || needSearch }, "גלה מקורות לחיפוש"),
    h("button", { className: "ghost", onClick: report, disabled: busy || needSearch }, "דוח חיפוש"),
    msg ? h("div", { className: "err" }, msg) : null,
    ans ? h("pre", { style: { whiteSpace: "pre-wrap", direction: "rtl" } }, ans.answer + (ans.mode === "llm" ? "\n(נוסח ע״י מודל שפה חינמי)" : "")) : null,
    rep ? h("pre", { style: { whiteSpace: "pre-wrap", direction: "rtl" } }, "סה״כ " + rep.total + " · פעילות " + rep.new + " · נפסלו " + rep.rejected + " · ציון ממוצע " + rep.avg_score + "%" + (rep.price ? "\nמחיר חציוני " + Math.round(rep.price.median).toLocaleString() : "") + (Object.keys(rep.cities || {}).length ? "\nערים: " + Object.entries(rep.cities).map(([k, v]) => k + " (" + v + ")").join(", ") : "")) : null,
    sug ? h("div", null, h("p", null, "חיפוש: " + sug.query),
      ...sug.suggestions.map((x: any) => h("div", { key: x.id, className: "risk", style: { display: "block" } }, x.label + (x.needs_input ? " (דורש כתובת שלך: " + x.url_template + ")" : "") + " — " + x.note)),
      h("button", { onClick: apply, disabled: busy }, "הוסף את כל המקורות האוטומטיים")) : null);
}
