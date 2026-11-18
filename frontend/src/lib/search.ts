// Pure helpers (unit-tested with `npm test`, no dependencies).
export type ParsedSearch = {
  name: string | null; category: string | null; location: string | null;
  min_price: number | null; max_price: number | null;
  required_keywords: string[]; excluded_keywords: string[]; min_score: number;
};
import { CATALOG } from "./catalog.ts";
// The original six keep their labels and order; the registry (49 categories) is appended.
export const CATEGORIES: Record<string, string> = { real_estate: "נדל״ן", vehicles: "רכב", electronics: "אלקטרוניקה", business: "עסקים", services: "שירותים", other: "אחר", ...Object.fromEntries(CATALOG.filter(c => !["real_estate", "vehicles", "electronics", "business", "services", "other"].includes(c.key)).map(c => [c.key, c.label])) };

export function toSearchBody(p: ParsedSearch, categoryFallback?: string) {
  const category = p.category || categoryFallback || "";
  if (!category) throw new Error("חסר סוג הזדמנות");
  return {
    name: (p.name || "חיפוש חדש").slice(0, 120), category,
    location: p.location || null, min_price: p.min_price, max_price: p.max_price,
    required_keywords: p.required_keywords, excluded_keywords: p.excluded_keywords, min_score: p.min_score,
  };
}
export function fmtPrice(v: number | null | undefined, cur?: string | null): string {
  if (v == null) return "?";
  return new Intl.NumberFormat("he-IL").format(v) + (cur === "ILS" || !cur ? " ₪" : " " + cur);
}
export function isHttpsUrl(s: string): boolean {
  try { const u = new URL(s); return u.protocol === "https:" || u.protocol === "http:"; } catch { return false; }
}
export function passwordProblem(pw: string): string | null {
  return pw.length < 10 ? "הסיסמה חייבת להכיל לפחות 10 תווים" : null;
}
