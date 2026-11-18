// Pure sign-in helpers (unit-tested). Mirrors backend/app/authsec.py so the user sees the reason before the server has to say no.
const COMMON = new Set(["password", "password1", "password12", "password123", "1234567890", "12345678910", "0123456789", "qwertyuiop", "qwerty12345", "qwerty123456", "iloveyou12", "letmein123", "welcome123", "admin12345", "administrator", "abcdefghij", "abc1234567", "1q2w3e4r5t", "changeme123", "p@ssw0rd123", "passw0rd123", "israel12345", "shalom12345", "sniper12345", "smartsniper"]);
export const MIN_LEN = 10, MAX_BYTES = 72;
const bytes = (s: string) => new TextEncoder().encode(s).length;
function sequential(p: string): boolean {
  const s = p.toLowerCase(); if (new Set(s).size <= 3) return true;
  let run = 1; for (let i = 1; i < s.length; i++) { run = Math.abs(s.charCodeAt(i) - s.charCodeAt(i - 1)) === 1 ? run + 1 : 1; if (run >= 6) return true; }
  return false;
}
/** Hebrew reasons a password would be refused (empty = acceptable). */
export function passwordIssues(pw: string, email = ""): string[] {
  const out: string[] = [], low = pw.toLowerCase(), local = email.split("@")[0].toLowerCase();
  if (pw.length < MIN_LEN) out.push(`לפחות ${MIN_LEN} תווים`);
  if (bytes(pw) > MAX_BYTES) out.push(`עד ${MAX_BYTES} בתים`);
  if (pw && pw.trim() !== pw) out.push("בלי רווח בתחילה או בסוף");
  if (pw && (COMMON.has(low) || COMMON.has(low.replace(/\d+$/, "")))) out.push("סיסמה נפוצה מדי");
  else if (pw.length >= 4 && sequential(pw)) out.push("בלי רצף או תו חוזר");
  if (local.length >= 4 && low.includes(local)) out.push("לא להכיל את שם האימייל");
  if (pw && !(/[A-Za-z\u05d0-\u05ea]/.test(pw) && /\d|[^\w\s]/.test(pw))) out.push("אותיות וגם מספר או סימן");
  return out;
}
/** 0..100 for the strength bar. */
export function passwordStrength(pw: string): number {
  if (!pw) return 0;
  let s = Math.min(pw.length, 16) * 4 + 10 * [/[a-z]/, /[A-Z]/, /\d/, /[^\w\s]/].filter(r => r.test(pw)).length;
  if (COMMON.has(pw.toLowerCase())) s -= 30;
  return Math.max(0, Math.min(100, s));
}
export function strengthLabel(n: number): { text: string; level: 0 | 1 | 2 | 3 } {
  return n < 40 ? { text: "חלשה", level: 0 } : n < 65 ? { text: "בינונית", level: 1 } : n < 85 ? { text: "טובה", level: 2 } : { text: "חזקה", level: 3 };
}
export function emailProblem(e: string): string | null {
  const v = e.trim(); if (!v) return "נא להזין אימייל";
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v) && v.length <= 254 ? null : "כתובת האימייל אינה תקינה";
}
/** Turns whatever the API (or the browser) returned into a sentence a person can act on. */
export function friendlyError(status: number | null, detail: unknown, networkFailed = false): string {
  if (networkFailed) return "אין חיבור לשרת. אם זו הפעם הראשונה בזמן האחרון, ייתכן שהשרת מתעורר: המתינו כחצי דקה ונסו שוב.";
  if (Array.isArray(detail)) {
    const t = detail.map((d: any) => String(d?.msg || "")).join(" ").toLowerCase();
    if (t.includes("email")) return "כתובת האימייל אינה תקינה";
    if (t.includes("at least") || t.includes("characters")) return `הסיסמה קצרה מדי: לפחות ${MIN_LEN} תווים`;
    return "הפרטים שהוזנו אינם תקינים";
  }
  if (typeof detail === "string" && /[\u05d0-\u05ea]/.test(detail)) return detail;
  switch (status) {
    case 401: return "אימייל או סיסמה שגויים";
    case 409: return "כתובת האימייל כבר רשומה. נסו להתחבר";
    case 422: return "הפרטים שהוזנו אינם תקינים";
    case 429: return "יותר מדי ניסיונות. המתינו מספר דקות ונסו שוב";
    case 502: case 503: case 504: return "השרת אינו זמין כרגע. נסו שוב בעוד רגע";
    default: return status && status >= 500 ? "שגיאת שרת זמנית. נסו שוב" : typeof detail === "string" && detail ? detail : "משהו השתבש. נסו שוב";
  }
}
/** API base: build-time VITE_API_URL, else a runtime value from /config.js (editable without rebuilding), else same origin. */
export function resolveApiBase(buildTime: string | undefined, runtime: string | undefined): string {
  return String(buildTime || runtime || "").trim().replace(/\/+$/, "");
}
