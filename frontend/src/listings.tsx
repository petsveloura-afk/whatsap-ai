import { useEffect, useMemo, useState } from "react";
import { fmtPrice } from "./lib/search";

type Api = (path: string, o?: any) => Promise<any>;

/** Tiny inline icon set (no dependency). */
const PATHS: Record<string, string> = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  target: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 16a4 4 0 100-8 4 4 0 000 8zM12 12h.01",
  bot: "M12 3v3M7 8h10a3 3 0 013 3v5a3 3 0 01-3 3H7a3 3 0 01-3-3v-5a3 3 0 013-3zM9 13h.01M15 13h.01M9 17h6",
  radar: "M12 12l6-6M12 21a9 9 0 119-9M12 17a5 5 0 115-5M12 12h.01",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4",
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z",
  chat: "M4 5h16v11H9l-5 4V5zM8 9h8M8 12h5",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  send: "M21 3L3 11l7 2 2 7 9-17zM10 13l11-10",
  link: "M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z",
  x: "M6 6l12 12M18 6L6 18",
  check: "M5 12l5 5 9-10",
  copy: "M9 9h11v11H9zM5 15V4h11",
  bell: "M6 17V11a6 6 0 1112 0v6l2 2H4l2-2zM10 21h4",
  bolt: "M13 3L4 14h7l-1 7 9-11h-7l1-7z",
  search: "M11 18a7 7 0 100-14 7 7 0 000 14zM21 21l-5-5",
  layers: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5",
  download: "M12 4v11M7 11l5 5 5-5M5 20h14",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z",
  card: "M3 6h18v12H3zM3 10h18M7 15h3",
  logout: "M9 4H5v16h4M15 8l5 4-5 4M20 12H9",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12l2-1-1-3-2 .4a7 7 0 00-1.6-1.6L16.8 5l-3-1-1 2a7 7 0 00-2.2 0l-1-2-3 1 .4 2A7 7 0 005.4 8L3.4 8l-1 3 2 1a7 7 0 000 2.2l-2 1 1 3 2-.4a7 7 0 001.6 1.6L7.2 21l3 1 1-2a7 7 0 002.2 0l1 2 3-1-.4-2a7 7 0 001.6-1.6l2 .4 1-3-2-1z",
  spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18",
};
export function Icon({ n }: { n: string }) {
  return <svg className="ico" viewBox="0 0 24 24" aria-hidden="true"><path d={PATHS[n] || PATHS.spark} /></svg>;
}

export const STATUS_HE: Record<string, string> = { new: "חדש", saved: "נשמר", contacted: "נוצר קשר", rejected: "נדחה", purchased: "נסגר" };
const COND_HE: Record<string, string> = { renovated: "משופצת", needs_renovation: "דורשת שיפוץ", new: "חדשה" };

/** Everything the card needs, with safe fallbacks so an older server (no `contact` field) still renders. */
export function contactOf(l: any) {
  const c = l.contact || {};
  return { phones: c.phones || [], emails: c.emails || [], wa: c.whatsapp_links || [], tg: c.telegram_links || [], source: c.source || (l.source_url ? { url: l.source_url, host: hostOf(l.source_url) } : null) };
}
export function hostOf(u: string) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } }
export function titleOf(l: any) {
  const x = l.extracted || {};
  const parts = [x.rooms != null ? `${x.rooms} חד׳` : "", x.location || ""].filter(Boolean);
  return l.title && l.title.length > 3 ? l.title : parts.join(" · ") || "הזדמנות";
}
export function waText(l: any) {
  const x = l.extracted || {};
  return `שלום, ראיתי את המודעה${x.location ? " ב" + x.location : ""}${x.price ? " (" + fmtPrice(x.price, x.currency) + ")" : ""}. האם עדיין רלוונטי?`;
}


let rememberedName = "";   // kept for the session only, so the signature is typed once
/** Draft of a first message to the owner. Nothing is sent by us: WhatsApp / mail open with the text and the user presses send there. */
function Composer({ l, c, api, onToast, contacted }: { l: any; c: any; api: Api; onToast: (m: string) => void; contacted: () => void }) {
  const [tone, setTone] = useState("friendly"), [variant, setVariant] = useState(0), [name, setName] = useState(rememberedName), [text, setText] = useState(waText(l));
  const [busy, setBusy] = useState(false), [ai, setAi] = useState(false);
  const load = async (t: string, v: number, polish = false) => {
    try { setBusy(true); const r = await api(`/api/listings/${l.id}/draft?tone=${t}&variant=${v}&name=${encodeURIComponent(name)}${polish ? "&polish=true" : ""}`); setText(r.text); setAi(!!r.ai); if (polish && !r.ai) onToast("ניסוח AI לא זמין כרגע, נשארה הטיוטה הרגילה"); }
    catch { onToast("לא ניתן להכין טיוטה כרגע"); } finally { setBusy(false); }
  };
  useEffect(() => { load(tone, variant); }, []);
  const pick = (t: string) => { setTone(t); setVariant(0); load(t, 0); };
  const another = () => { const v = variant + 1; setVariant(v); load(tone, v); };
  const copy = async () => { try { await navigator.clipboard.writeText(text); onToast("ההודעה הועתקה"); } catch { onToast("לא ניתן להעתיק כאן"); } };
  const enc = encodeURIComponent(text);
  return (
    <div className="outbox" aria-label="הכנת הודעה">
      <h5>הודעה לבעל המודעה</h5>
      <div className="c-row">
        {([["friendly", "ידידותי"], ["formal", "רשמי"], ["short", "קצר"]] as [string, string][]).map(([k, n]) => <button key={k} className={"ghost sm" + (tone === k ? " on" : "")} onClick={() => pick(k)} disabled={busy}>{n}</button>)}
        <button className="ghost sm" onClick={another} disabled={busy}>ניסוח אחר</button>
        <button className="ghost sm" onClick={() => load(tone, variant, true)} disabled={busy}>שפר ב-AI</button>
      </div>
      <input value={name} maxLength={40} placeholder="השם שלך (לחתימה, אופציונלי)" onChange={e => { setName(e.target.value); rememberedName = e.target.value; }} onBlur={() => load(tone, variant)} />
      <textarea rows={5} style={{ width: "100%" }} value={text} onChange={e => setText(e.target.value)} aria-label="נוסח ההודעה" />
      {ai && <div className="faint">נוסח בעזרת AI. קרא ותקן לפני שליחה.</div>}
      <div className="c-row">
        {c.phones.filter((p: any) => p.whatsapp).map((p: any) => <a key={p.tel} className="btn wa sm" href={p.whatsapp + "?text=" + enc} target="_blank" rel="noopener noreferrer" onClick={contacted}><Icon n="chat" />שלח בוואטסאפ ל-{p.display}</a>)}
        {c.emails.map((m: string) => <a key={m} className="btn mail sm" href={`mailto:${m}?subject=${encodeURIComponent("בנוגע למודעה: " + titleOf(l))}&body=${enc}`} onClick={contacted}><Icon n="mail" />שלח במייל</a>)}
        <button className="ghost sm" onClick={copy}><Icon n="copy" />העתק</button>
      </div>
      <div className="faint">ההודעה נפתחת באפליקציה שלך ויוצאת רק כשאתה לוחץ "שלח" שם. המערכת לא שולחת דבר בעצמה.</div>
    </div>
  );
}

/** One opportunity: score ring, key facts, why it matched, and one-tap ways to reach the owner. */
export function ListingCard({ l, act, api, onToast }: { l: any; act: (fn: () => Promise<any>) => Promise<void>; api: Api; onToast: (m: string) => void }) {
  const [open, setOpen] = useState(false), [compose, setCompose] = useState(false);
  const x = l.extracted || {}, c = contactOf(l);
  const hasDirect = c.phones.length || c.emails.length || c.wa.length || c.tg.length;
  const mark = (k: string) => act(() => api(`/api/listings/${l.id}/${k}`, { method: "POST" }));
  const copy = async () => {
    const text = [titleOf(l), x.price ? fmtPrice(x.price, x.currency) : "", ...c.phones.map((p: any) => p.display), ...c.emails, c.source?.url || ""].filter(Boolean).join("\n");
    try { await navigator.clipboard.writeText(text); onToast("הפרטים הועתקו"); } catch { onToast("לא ניתן להעתיק כאן"); }
  };
  const contacted = () => { if (l.status !== "contacted") mark("contacted"); };
  return (
    <article className={"lcard " + l.status} aria-label={titleOf(l)}>
      <div className="l-head">
        <span className="score lg" style={{ "--p": l.score } as any} aria-label={`התאמה ${l.score}%`}>{l.score}</span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h4 className="l-title">{titleOf(l)}</h4>
          <div className="l-sub"><span className={"status " + l.status}>{STATUS_HE[l.status] || l.status}</span>{c.source?.host && <span className="faint">מקור: {c.source.host}</span>}</div>
        </div>
      </div>
      <div className="l-tags">
        {x.price != null && <span className="tag price">{fmtPrice(x.price, x.currency)}</span>}
        {x.location && <span className="tag">📍 {x.location}</span>}
        {x.rooms != null && <span className="tag">{x.rooms} חדרים</span>}
        {x.condition && <span className="tag">{COND_HE[x.condition] || x.condition}</span>}
        {x.broker === false && <span className="tag good">ללא תיווך</span>}
        {x.broker === true && <span className="tag">תיווך</span>}
        {(l.highlights || []).map((h: string) => <span className="tag good" key={h}>✓ {h}</span>)}
        {(l.risks || []).map((r: string) => <span className="risk" key={r}>⚠ {r}</span>)}
        {l.status === "rejected" && (l.reasons || []).map((r: string) => <span className="tag" key={r}>{r}</span>)}
      </div>
      {l.summary && <p className={"l-sum" + (open ? " open" : "")}>{open && l.raw_text ? l.raw_text : l.summary}</p>}
      <div className="contact" aria-label="יצירת קשר">
        <h5>יצירת קשר</h5>
        {hasDirect ? <>
          {c.phones.map((p: any) => (
            <div className="c-row" key={p.tel}>
              <span className="c-num">{p.display}</span>
              <a className="btn call sm" href={"tel:" + p.tel} onClick={contacted}><Icon n="phone" />התקשר</a>
              {p.whatsapp && <a className="btn wa sm" href={p.whatsapp + "?text=" + encodeURIComponent(waText(l))} target="_blank" rel="noopener noreferrer" onClick={contacted}><Icon n="chat" />וואטסאפ</a>}
            </div>
          ))}
          <div className="c-row">
            {c.wa.map((u: string) => <a className="btn wa sm" key={u} href={u} target="_blank" rel="noopener noreferrer" onClick={contacted}><Icon n="chat" />קבוצה / צ׳אט וואטסאפ</a>)}
            {c.tg.map((u: string) => <a className="btn tg sm" key={u} href={u} target="_blank" rel="noopener noreferrer" onClick={contacted}><Icon n="send" />טלגרם</a>)}
            {c.emails.map((m: string) => <a className="btn mail sm" key={m} href={`mailto:${m}?subject=${encodeURIComponent("בנוגע למודעה: " + titleOf(l))}&body=${encodeURIComponent(waText(l))}`} onClick={contacted}><Icon n="mail" />{m}</a>)}
          </div>
        </> : (
          <div className="c-none">
            <span>במודעה לא פורסם טלפון או אימייל. הפרטים נמצאים בדרך כלל בעמוד המקור.</span>
          </div>
        )}
        <div className="c-row">
          {c.source ? <a className="btn src sm" href={c.source.url} target="_blank" rel="noopener noreferrer nofollow" onClick={contacted}><Icon n="link" />פתח את המודעה{c.source.host ? " ב-" + c.source.host : ""}</a>
            : !hasDirect && <span className="faint">אין קישור למקור. הדבק את המודעה המלאה (כולל הטלפון) כדי לקבל כפתורי יצירת קשר.</span>}
          <button className="ghost sm" onClick={copy}><Icon n="copy" />העתק פרטים</button>
        </div>
      </div>
      {compose && <Composer l={l} c={c} api={api} onToast={onToast} contacted={contacted} />}
      <div className="l-actions">
        {hasDirect && <button className="ghost sm" onClick={() => setCompose(!compose)}><Icon n="send" />{compose ? "סגור הודעה" : "הכן הודעה"}</button>}
        <button className="ghost sm" onClick={() => mark("save")} disabled={l.status === "saved"}><Icon n="star" />שמור</button>
        <button className="ghost sm" onClick={() => mark("contacted")} disabled={l.status === "contacted"}><Icon n="check" />יצרתי קשר</button>
        <button className="ghost sm" onClick={() => mark("purchased")} disabled={l.status === "purchased"}><Icon n="bolt" />נסגר</button>
        <span className="sp" />
        {l.summary && <button className="ghost sm" onClick={() => setOpen(!open)}>{open ? "פחות" : "הטקסט המלא"}</button>}
        <button className="danger sm" onClick={() => mark("reject")} disabled={l.status === "rejected"}><Icon n="x" />דחה</button>
      </div>
    </article>
  );
}

const SORTS: [string, string][] = [["score", "התאמה"], ["new", "חדש ביותר"], ["price_asc", "מחיר ↑"], ["price_desc", "מחיר ↓"]];
const FILTERS: [string, string][] = [["active", "פעילות"], ["new", "חדשות"], ["saved", "שמורות"], ["contacted", "נוצר קשר"], ["rejected", "נדחו"], ["all", "הכול"]];

/** Filter / sort / search toolbar + card grid for the opportunities tab. */
export function Opportunities({ listings, searches, api, act, onToast, goDiscover }: { listings: any[]; searches: any[]; api: Api; act: (fn: () => Promise<any>) => Promise<void>; onToast: (m: string) => void; goDiscover: () => void }) {
  const [flt, setFlt] = useState("active"), [sort, setSort] = useState("score"), [q, setQ] = useState(""), [min, setMin] = useState(0), [sid, setSid] = useState(""), [onlyContact, setOnlyContact] = useState(false);
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    let r = listings.filter(l => {
      if (flt === "active" ? l.status === "rejected" : flt !== "all" && l.status !== flt) return false;
      if (sid && l.search_id && l.search_id !== sid) return false;
      if (l.score < min) return false;
      if (onlyContact) { const c = contactOf(l); if (!(c.phones.length || c.emails.length || c.wa.length || c.tg.length || c.source)) return false; }
      if (t && !(`${titleOf(l)} ${l.summary || ""} ${l.extracted?.location || ""}`.toLowerCase().includes(t))) return false;
      return true;
    });
    const price = (l: any) => l.extracted?.price ?? Infinity;
    r = [...r].sort((a, b) => sort === "new" ? String(b.created_at || "").localeCompare(String(a.created_at || "")) : sort === "price_asc" ? price(a) - price(b) : sort === "price_desc" ? (price(b) === Infinity ? -1 : price(b)) - (price(a) === Infinity ? -1 : price(a)) : b.score - a.score);
    return r;
  }, [listings, flt, sort, q, min, sid, onlyContact]);
  const counts: Record<string, number> = { all: listings.length, active: listings.filter(l => l.status !== "rejected").length };
  for (const l of listings) counts[l.status] = (counts[l.status] || 0) + 1;
  return (
    <div>
      <div className="toolbar" role="search">
        <div className="seg" role="group" aria-label="סינון לפי סטטוס">{FILTERS.map(([k, v]) => <button key={k} aria-pressed={flt === k} onClick={() => setFlt(k)}>{v}{counts[k] ? ` (${counts[k]})` : ""}</button>)}</div>
        <input className="grow" type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="חפש בתוצאות: עיר, מילה, רחוב..." aria-label="חיפוש בתוצאות" />
        <select value={sid} onChange={e => setSid(e.target.value)} aria-label="לפי חיפוש"><option value="">כל החיפושים</option>{searches.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <select value={sort} onChange={e => setSort(e.target.value)} aria-label="מיון">{SORTS.map(([k, v]) => <option key={k} value={k}>מיון: {v}</option>)}</select>
        <label className="range">התאמה מעל {min}<input type="range" min={0} max={95} step={5} value={min} onChange={e => setMin(Number(e.target.value))} /></label>
        <label className="range"><input type="checkbox" checked={onlyContact} onChange={e => setOnlyContact(e.target.checked)} />עם דרך ליצור קשר</label>
      </div>
      {rows.length === 0 ? (
        <div className="empty-big">
          <div className="orb" aria-hidden="true" />
          <h3>{listings.length === 0 ? "עוד אין הזדמנויות" : "אין תוצאות שמתאימות לסינון"}</h3>
          <p>{listings.length === 0 ? "צור חיפוש ואז הבא מודעות מהרשת או הדבק אותן. כל מודעה תקבל ציון וכפתורי יצירת קשר." : "נסה להוריד את סף ההתאמה או לבחור סטטוס אחר."}</p>
          {listings.length === 0 && <button onClick={goDiscover}><Icon n="radar" /> להבאת הזדמנויות</button>}
        </div>
      ) : <div className="lcards">{rows.map(l => <ListingCard key={l.id} l={l} act={act} api={api} onToast={onToast} />)}</div>}
    </div>
  );
}
