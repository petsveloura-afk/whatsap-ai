import { Fragment } from "react";
import { Icon } from "./listings";

/** Quick-start steps. `tab` is the dashboard tab the button jumps to (same keys as the main navigation). */
const STEPS: { icon: string; title: string; text: string; tab: string; cta: string }[] = [
  { icon: "search", title: "הגדר מה מחפשים", text: "באשף החיפוש כתוב בשפה חופשית, למשל: דירת 3 חדרים בחולון עד 5,500. המערכת תמלא מיקום, תקציב וחדרים, ואפשר לתקן לפני שמירה.", tab: "discover", cta: "לחיפושים" },
  { icon: "radar", title: "הבא מודעות", text: "הדבק מודעה או כמה מודעות יחד, חבר מקור RSS או JSON ציבורי, או הפעל גילוי מהרשת (דורש מפתח של מנוע חיפוש).", tab: "discover", cta: "להבאת מודעות" },
  { icon: "target", title: "סקור ודרג", text: "כל הזדמנות מקבלת ציון 0 עד 100, הסבר למה התאימה, וסימני אזהרה. שמור או דחה כדי שהמערכת תלמד מה מתאים לך.", tab: "opps", cta: "להזדמנויות" },
  { icon: "phone", title: "צור קשר", text: "התקשר, שלח וואטסאפ עם הודעה מוכנה, שלח מייל או פתח את המודעה במקור. המערכת לא שולחת הודעות בשמך.", tab: "opps", cta: "ליצירת קשר" },
  { icon: "bot", title: "דבר עם הסוכן", text: "הסוכן מנתח, יוצר חיפושים, מסמן מודעות וזוכר העדפות. אין לו כלי מחיקה, וכל פעולה שהוא עושה מדווחת לך.", tab: "agent", cta: "לסוכן" },
  { icon: "bolt", title: "כלים מתקדמים", text: "בדיקת הונאות, מחיר הוגן, עזרה במו״מ, מחשבוני משכנתא ותשואה, מעקב לקוחות ודוחות.", tab: "pro", cta: "לכלי פרו" },
];

const FAQ: [string, string][] = [
  ["מה אומר הציון?", "ציון התאמה בין 0 ל-100 לפי מה שהגדרת בחיפוש: מיקום, תקציב, חדרים ומילות מפתח. אם ההתאמה האישית פעילה, מה ששמרת ודחית יכול להזיז את הציון בעד 10 נקודות, וההסבר מופיע בפירוט ההזדמנות."],
  ["מה הם סימני אזהרה?", "אינדיקטורים בלבד ולא הוכחה: למשל בקשת מקדמה, ניסוח לחץ, מחיר חריג מאוד או קילומטראז׳ גבוה. לפני כל תשלום כדאי לוודא מול המוכר ולראות את הנכס או הרכב בעצמך."],
  ["למה אין לי תוצאות?", "המערכת לא גולשת באתרי מודעות. נתונים נכנסים רק מהדבקה ידנית, ממקורות RSS או JSON ציבוריים, או ממנוע חיפוש רשמי אם הוגדר מפתח. אם החיפוש ריק, התחל בהדבקת מודעה."],
  ["מה הסוכן זוכר עליי, ואיך מוחקים?", "הזיכרון מופיע בלשונית הסוכן ובפרופיל. אפשר למחוק כל פריט, לכבות את ההתאמה האישית, או לייצא ולמחוק את כל הנתונים. הזיכרון נמחק גם כשמוחקים את החשבון."],
  ["איך מפעילים את המוח החכם?", "מוסיפים בשרת מפתח חינמי אחד או יותר (Gemini, Groq ועוד) ומדליקים את הדגל llm_extraction בלשונית הניהול. בלי זה הסוכן ממשיך לעבוד בכללים מקומיים."],
  ["איך מתקינים כאפליקציה?", "ב-Android/Chrome: תפריט ← התקן אפליקציה. ב-iPhone: שיתוף ← הוסף למסך הבית."],
  ["האם הנתונים שלי פרטיים?", "כל נתון משויך לחשבון שלך בלבד. אפשר לייצא את כל המידע או למחוק את החשבון בלחיצה, מלשונית החשבון."],
];

/** In-app guide: quick start, FAQ (native <details>, keyboard and screen-reader friendly) and the keyboard shortcuts that really exist. */
export function GuidePanel({ onNavigate, tabs }: { onNavigate?: (tab: string) => void; tabs?: [string, string, string][] }) {
  return <section className="gd" aria-label="מדריך שימוש">
    <div className="gd-card">
      <h3>התחלה מהירה</h3>
      <ol className="gd-steps">
        {STEPS.map(s => <li key={s.title}><b><Icon n={s.icon} /> {s.title}</b><p>{s.text}</p>{onNavigate && <button type="button" className="ghost sm" onClick={() => onNavigate(s.tab)}>{s.cta}</button>}</li>)}
      </ol>
    </div>
    <div className="gd-card">
      <h3>שאלות נפוצות</h3>
      {FAQ.map(([q, a]) => <details key={q}><summary>{q}</summary><div>{a}</div></details>)}
    </div>
    <div className="gd-card">
      <h3>קיצורי מקלדת</h3>
      <dl className="gd-keys">
        {(tabs || []).slice(0, 9).map(([k, name], i) => <Fragment key={k}><dt><kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>{i + 1}</kbd></dt><dd>מעבר ללשונית {name}</dd></Fragment>)}
        <dt><kbd>Enter</kbd></dt><dd>שליחת הודעה לסוכן</dd>
        <dt><kbd>Shift</kbd> + <kbd>Enter</kbd></dt><dd>שורה חדשה בהודעה</dd>
        <dt><kbd>Tab</kbd></dt><dd>מעבר בין הכפתורים והשדות; הקישור הראשון בדף מדלג ישר לתוכן</dd>
      </dl>
    </div>
  </section>;
}
