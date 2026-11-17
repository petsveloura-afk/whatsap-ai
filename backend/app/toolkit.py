"""Pro toolkit (v3.13): 30+ sellable features that cost nothing to run (pure Python, no paid API, no new tables).
Everything here is a pure function: DB / HTTP wiring lives in routes_v7.py. Rule-based first, so every feature works with the AI switched off;
the AI brain (brains.py) is only an optional polish on top. Numbers marked 'indicative' are estimates, never legal or financial advice.

Plans: starter (free) < pro < vip. Each feature has a minimum plan and a small monthly free trial for lower plans, which is the upsell hook."""
import csv, datetime as dt, html as _html, io, json, math, os, re, statistics
from . import neardup

PLAN_RANK = {"starter": 0, "pro": 1, "vip": 2}
# id, hebrew name, hebrew description, min plan, monthly free trial for lower plans, group
FEATURES: list[dict] = [dict(id=i, name=n, desc=d, plan=p, trial=t, group=g) for i, n, d, p, t, g in [
    ("scan_plus", "סריקה מורחבת", "שאילתות חכמות בכמה ניסוחים ובכמה אתרי מודעות, דירוג מחדש וסינון זבל, עם דוח לכל שאילתה.", "pro", 3, "scan"),
    ("auto_scan", "סריקה אוטומטית", "החיפושים שלך נסרקים לבד כל כמה שעות והתוצאות מחכות לך בהזדמנויות.", "vip", 0, "scan"),
    ("scan_report", "בריאות מנועי חיפוש", "אילו מנועים פעילים, כמה נשאר בחבילה החינמית, והמלצה מה להוסיף.", "starter", 99, "scan"),
    ("smart_paste", "הדבקה חכמה", "מנקה הודעות מווטסאפ/פייסבוק (אימוג׳ים, שמות, שרשורים) ומפצל למודעות לפני ניתוח.", "starter", 99, "scan"),
    ("fraud_check", "בדיקת הונאה מתקדמת", "מזהה דפוסי הונאה (מקדמה, בעלים בחו״ל, לחץ, מחיר חשוד) ונותן ציון סיכון והסבר.", "starter", 99, "analysis"),
    ("fair_price", "מחיר הוגן ומחיר למ״ר", "טווח מחיר הוגן לפי מודעות דומות, מחיר למ״ר והפער מהשוק.", "pro", 5, "analysis"),
    ("negotiation", "עוזר משא ומתן", "טווח הצעה (פתיחה, יעד, סף יציאה) ותסריט מוכן בעברית, אנגלית, רוסית וערבית.", "pro", 3, "analysis"),
    ("compare", "השוואת הזדמנויות", "השוואה זה-לצד-זה לפי משקלים שאתה קובע, עם מנצח והסבר.", "pro", 3, "analysis"),
    ("dup_clusters", "איחוד כפילויות", "מזהה את אותו נכס שפורסם בכמה מקומות ומראה את הזול והאמין ביותר.", "pro", 3, "analysis"),
    ("smart_tags", "תגיות חכמות", "מחלץ מהטקסט חניה, מעלית, ממ״ד, מרפסת, שיפוץ, קומה ועוד כתגיות.", "starter", 99, "analysis"),
    ("checklist", "רשימת בדיקה לצפייה", "שאלות למוכר ודברים לבדוק במקום, מותאם לדירה, רכב או מוצר.", "starter", 99, "analysis"),
    ("ai_analyst", "אנליסט AI", "יתרונות, חסרונות ושאלות מפתח לכל מודעה (עם גיבוי כללים כשה-AI כבוי).", "vip", 3, "ai"),
    ("translate", "תרגום מודעה", "תרגום סיכום מודעה לאנגלית, רוסית, ערבית, צרפתית ועברית.", "pro", 3, "ai"),
    ("mortgage", "מחשבון משכנתא", "החזר חודשי, ריבית כוללת, תרחישי ריבית ולוח סילוקין שנתי.", "starter", 99, "calc"),
    ("affordability", "כוח קנייה", "כמה דירה אפשר לקנות לפי הכנסה, חיסכון והתחייבויות.", "starter", 99, "calc"),
    ("purchase_costs", "עלויות רכישה ומס רכישה", "מס רכישה לפי מדרגות, עו״ד, תיווך ועלויות נלוות: כמה מזומן באמת צריך.", "starter", 99, "calc"),
    ("yield", "תשואה והחזר השקעה", "תשואה ברוטו ונטו, שנות החזר ותזרים מול משכנתא.", "pro", 5, "calc"),
    ("vehicle_tco", "עלות בעלות על רכב", "עלות חודשית וכוללת: דלק, ביטוח, טיפולים, פחת.", "pro", 5, "calc"),
    ("used_price", "מחיר יד שנייה", "מחיר הוגן לאלקטרוניקה ורהיטים לפי גיל ומצב.", "starter", 99, "calc"),
    ("crm", "מעקב ו-CRM", "צינור מכירה לכל הזדמנות: נוצר קשר, צפייה, משא ומתן, נסגר. עם הערות.", "pro", 5, "crm"),
    ("reminders", "תזכורות מעקב", "תזכורת להתקשר שוב או לבוא לצפייה, כולל התראה באפליקציה.", "pro", 5, "crm"),
    ("alert_rules", "כללי התראה", "כללים משלך (עיר, מחיר, חדרים, מילים, ציון) שמתריעים על הזדמנות מתאימה.", "pro", 2, "crm"),
    ("clients", "לקוחות והתאמה", "פרופיל לקוח (תקציב, אזור, חדרים) והתאמת הזדמנויות אליו עם הודעה מוכנה. למתווכים.", "vip", 0, "crm"),
    ("templates", "הודעות בכמה שפות", "הודעת פנייה, מעקב, הצעה, תיאום צפייה ותודה בעברית, אנגלית, רוסית וערבית.", "starter", 99, "crm"),
    ("deal_sheet", "דף עסקה ממותג", "דף נקי להדפסה או שליחה ללקוח, עם השם והצבע של העסק שלך.", "vip", 1, "reports"),
    ("csv_export", "ייצוא CSV", "כל ההזדמנויות לקובץ שנפתח באקסל (עם הגנה מהזרקת נוסחאות).", "pro", 3, "reports"),
    ("market_report", "דוח שוק", "חציון, טווחים ומחיר למ״ר לפי עיר וחדרים, ההזדמנויות הזולות ומגמה.", "pro", 3, "reports"),
    ("share_pack", "חבילת שיתוף", "טקסט מוכן לווטסאפ, טלגרם ומייל על הזדמנות, כולל המיתוג שלך.", "pro", 3, "reports"),
    ("weekly_brief", "תקציר שבועי", "הזדמנויות מובילות, סטטיסטיקה ומה השתנה, בנוסח מוכן לשליחה.", "pro", 3, "reports"),
    ("white_label", "מיתוג עסקי", "שם עסק, טלפון, מייל וצבע שמופיעים בדפים ובהודעות שאתה שולח.", "vip", 0, "reports"),
]]
FEATURE_IDS = {f["id"] for f in FEATURES}
GROUPS = {"scan": "סריקה ואוטומציה", "analysis": "ניתוח הזדמנות", "ai": "בינה מלאכותית", "calc": "מחשבונים", "crm": "מעקב ולקוחות", "reports": "דוחות ומיתוג"}


def feature(fid: str) -> dict | None: return next((f for f in FEATURES if f["id"] == fid), None)
def month_key(now: dt.datetime | None = None) -> str: return (now or dt.datetime.utcnow()).strftime("%Y%m")


def access(fid: str, plan: str, used: int, open_all: bool = False) -> dict:
    """-> {allowed, reason, trial_left}. Higher plans are unlimited; lower plans get a small monthly trial (the upsell hook)."""
    f = feature(fid)
    if not f: return {"allowed": False, "reason": "unknown_feature", "trial_left": 0}
    if open_all or PLAN_RANK.get(plan, 0) >= PLAN_RANK[f["plan"]]: return {"allowed": True, "reason": "plan", "trial_left": None}
    left = max(0, f["trial"] - used)
    return {"allowed": left > 0, "reason": "trial" if left else "upgrade", "trial_left": left}


def _n(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d


def _ils(x) -> str: return f"{x:,.0f} ₪"
def _clamp(x, lo, hi): return max(lo, min(hi, x))


# ================================================================== money calculators
def _pmt(principal: float, rate_pct: float, years: float) -> float:
    n = int(round(years * 12)); r = rate_pct / 100 / 12
    if n <= 0: return 0.0
    return principal / n if r == 0 else principal * r / (1 - (1 + r) ** -n)


def _pv(payment: float, rate_pct: float, years: float) -> float:
    n = int(round(years * 12)); r = rate_pct / 100 / 12
    return payment * n if r == 0 else payment * (1 - (1 + r) ** -n) / r


LTV_CAP = {"first": 75.0, "upgrade": 70.0, "investment": 50.0}      # indicative Bank-of-Israel style caps; the bank decides
KIND_HE = {"first": "דירה ראשונה", "upgrade": "משפר דיור", "investment": "דירה להשקעה"}


def mortgage(price: float, down_payment: float | None = None, ltv_pct: float | None = None, rate_pct: float = 4.5, years: float = 25, income_monthly: float = 0, kind: str = "first") -> dict:
    price = _clamp(_n(price), 0, 1e10); years = _clamp(_n(years, 25), 1, 40); rate = _clamp(_n(rate_pct, 4.5), 0, 25)
    if price <= 0: raise ValueError("price must be positive")
    loan = price - _n(down_payment) if down_payment is not None else price * _clamp(_n(ltv_pct, 75), 0, 100) / 100
    loan = _clamp(loan, 0, price); pay = _pmt(loan, rate, years); n = int(round(years * 12)); total = pay * n
    r = rate / 100 / 12; bal = loan; sched = []; yi = yp = 0.0
    for m in range(1, n + 1):
        i = bal * r; p = pay - i; bal = max(0.0, bal - p); yi += i; yp += p
        if m % 12 == 0 or m == n: sched.append({"year": math.ceil(m / 12), "principal": round(yp), "interest": round(yi), "balance": round(bal)}); yi = yp = 0.0
    out = {"price": round(price), "loan": round(loan), "down_payment": round(price - loan), "ltv_pct": round(loan / price * 100, 1), "monthly": round(pay), "total_paid": round(total),
           "total_interest": round(total - loan), "months": n, "schedule": sched,
           "scenarios": [{"rate_pct": round(rate + d, 2), "monthly": round(_pmt(loan, rate + d, years))} for d in (-1, -0.5, 0.5, 1, 2) if rate + d >= 0], "warnings": []}
    cap = LTV_CAP.get(kind, 75.0)
    if out["ltv_pct"] > cap: out["warnings"].append(f"מימון של {out['ltv_pct']}% גבוה מהתקרה המקובלת ({cap:.0f}%) ל{KIND_HE.get(kind, kind)}. הבנק יקבע בפועל.")
    if income_monthly and pay / income_monthly > 0.33: out["warnings"].append(f"ההחזר הוא {pay / income_monthly * 100:.0f}% מההכנסה. בנקים בדרך כלל מגבילים לכשליש.")
    if income_monthly: out["pti_pct"] = round(pay / income_monthly * 100, 1)
    return out


_DEFAULT_TAX = {"single": [[1978745, 0.0], [2347040, 0.035], [6055070, 0.05], [20183565, 0.08], [None, 0.10]], "additional": [[6055070, 0.08], [None, 0.10]]}
TAX_NOTE = "מדרגות 2026 (קפואות עד ינואר 2028). שיעורי דירה נוספת נקבעו בהוראת שעה לסוף 2026: בדוק מול רשות המסים או עורך דין לפני עסקה."


def tax_brackets() -> dict:
    raw = os.environ.get("TAX_BRACKETS_JSON")
    if raw:
        try:
            d = json.loads(raw)
            if isinstance(d.get("single"), list) and isinstance(d.get("additional"), list): return d
        except Exception: pass
    return _DEFAULT_TAX


def purchase_tax(price: float, kind: str = "single") -> float:
    """Layered ('מדרגתי') tax: each rate applies only to the slice inside its bracket."""
    prev = 0.0; tax = 0.0
    for limit, rate in tax_brackets().get("additional" if kind == "additional" else "single"):
        top = price if limit is None else min(price, float(limit))
        if top > prev: tax += (top - prev) * float(rate)
        prev = float(limit) if limit is not None else price
        if limit is None or price <= float(limit): break
    return tax


def purchase_costs(price: float, kind: str = "single", broker: bool = False, lawyer_pct: float = 0.5, broker_pct: float = 2.0, vat_pct: float = 18.0,
                   appraiser: float = 0, renovation: float = 0, moving: float = 0, down_payment: float | None = None) -> dict:
    price = _clamp(_n(price), 0, 1e10)
    if price <= 0: raise ValueError("price must be positive")
    tax = purchase_tax(price, kind); vat = 1 + _clamp(_n(vat_pct, 18), 0, 30) / 100
    lawyer = price * _clamp(_n(lawyer_pct, 0.5), 0, 3) / 100 * vat
    brk = price * _clamp(_n(broker_pct, 2), 0, 5) / 100 * vat if broker else 0.0
    items = [{"name": "מס רכישה", "amount": round(tax)}, {"name": "עורך דין (כולל מע״מ)", "amount": round(lawyer)}]
    if broker: items.append({"name": "תיווך (כולל מע״מ)", "amount": round(brk)})
    for nm, v in (("שמאי", appraiser), ("שיפוץ", renovation), ("הובלה ומעבר", moving)):
        if _n(v) > 0: items.append({"name": nm, "amount": round(_n(v))})
    extra = sum(i["amount"] for i in items)
    out = {"price": round(price), "kind": kind, "items": items, "extra_total": extra, "extra_pct": round(extra / price * 100, 2), "all_in": round(price + extra), "note": TAX_NOTE}
    if down_payment is not None: out["cash_needed"] = round(_n(down_payment) + extra)
    return out


def affordability(income_monthly: float, savings: float, loans_monthly: float = 0, kind: str = "first", rate_pct: float = 4.5, years: float = 25, pti_pct: float = 33.0, broker: bool = False) -> dict:
    inc = _n(income_monthly); sav = _n(savings)
    if inc <= 0: raise ValueError("income must be positive")
    pay_cap = max(0.0, inc * _clamp(_n(pti_pct, 33), 10, 50) / 100 - _n(loans_monthly)); loan_cap = _pv(pay_cap, rate_pct, years); ltv = LTV_CAP.get(kind, 75.0) / 100
    tax_kind = "additional" if kind == "investment" else "single"; lo, hi = 0.0, 5e7
    for _ in range(60):
        mid = (lo + hi) / 2; loan = min(mid * ltv, loan_cap); need = mid - loan + purchase_costs(mid, tax_kind, broker)["extra_total"]
        if need <= sav: lo = mid
        else: hi = mid
    price = lo; loan = min(price * ltv, loan_cap); pc = purchase_costs(price, tax_kind, broker) if price > 0 else {"extra_total": 0}
    why = "ההכנסה מגבילה (ההחזר החודשי)" if loan_cap < price * ltv - 1 else "ההון העצמי מגביל"
    return {"max_price": round(price, -3), "loan": round(loan), "monthly": round(_pmt(loan, rate_pct, years)), "equity_used": round(price - loan), "extra_costs": pc["extra_total"],
            "max_monthly_payment": round(pay_cap), "limited_by": why, "kind": kind, "ltv_pct": LTV_CAP.get(kind, 75.0),
            "tip": "הערכה בלבד. אשר מול יועץ משכנתאות או הבנק לפני שמחליטים.", "note": TAX_NOTE}


def rental_yield(price: float, monthly_rent: float, annual_costs: float = 0, vacancy_pct: float = 4, purchase_extra: float | None = None, loan: float = 0, rate_pct: float = 4.5, years: float = 25, kind: str = "investment") -> dict:
    price = _n(price); rent = _n(monthly_rent)
    if price <= 0 or rent <= 0: raise ValueError("price and rent must be positive")
    extra = purchase_costs(price, "additional" if kind == "investment" else "single")["extra_total"] if purchase_extra is None else _n(purchase_extra)
    gross = rent * 12; eff = gross * (1 - _clamp(_n(vacancy_pct, 4), 0, 50) / 100); net = eff - _n(annual_costs); invest = price + extra
    out = {"gross_yield_pct": round(gross / price * 100, 2), "net_yield_pct": round(net / invest * 100, 2), "annual_net": round(net), "invested": round(invest), "purchase_extra": round(extra),
           "payback_years": round(invest / net, 1) if net > 0 else None, "verdict": ""}
    if loan:
        pay = _pmt(_n(loan), rate_pct, years); out["monthly_payment"] = round(pay); out["monthly_cashflow"] = round(net / 12 - pay)
        out["cash_invested"] = round(invest - _n(loan)); out["cash_on_cash_pct"] = round((net - pay * 12) / max(1.0, invest - _n(loan)) * 100, 2)
    ny = out["net_yield_pct"]; out["verdict"] = "תשואה נמוכה" if ny < 2.5 else "תשואה בינונית" if ny < 4 else "תשואה טובה" if ny < 6 else "תשואה גבוהה (בדוק שהשכירות מציאותית)"
    return out


def vehicle_tco(price: float, years: float = 4, km_year: float = 15000, l_per_100: float = 7.5, fuel_price: float = 7.5, insurance_year: float = 4500,
                license_year: float = 1800, maintenance_year: float = 3000, resale_pct: float | None = None, loan: float = 0, rate_pct: float = 5.5) -> dict:
    price = _n(price); years = _clamp(_n(years, 4), 0.5, 15)
    if price <= 0: raise ValueError("price must be positive")
    resale = _clamp(_n(resale_pct), 0, 100) / 100 if resale_pct is not None else max(0.15, 0.82 ** years)      # rough exponential depreciation when not given
    deprec = price * (1 - resale); km = _n(km_year) * years; fuel = km / 100 * _n(l_per_100) * _n(fuel_price)
    fixed = (_n(insurance_year) + _n(license_year) + _n(maintenance_year)) * years; fin = _pmt(_n(loan), rate_pct, years) * years * 12 - _n(loan) if loan else 0.0
    total = deprec + fuel + fixed + fin
    return {"years": years, "total": round(total), "per_month": round(total / (years * 12)), "per_km": round(total / km, 2) if km else None, "resale_value": round(price * resale),
            "breakdown": [{"name": "פחת", "amount": round(deprec)}, {"name": "דלק", "amount": round(fuel)}, {"name": "ביטוח, רישוי וטיפולים", "amount": round(fixed)}] + ([{"name": "עלות מימון", "amount": round(fin)}] if fin else []),
            "note": "הערכה. מחירי דלק וביטוח משתנים, עדכן את השדות לפי המציאות."}


_DEPR = {"phone": (0.30, 0.20), "laptop": (0.28, 0.18), "tv": (0.22, 0.12), "appliance": (0.20, 0.10), "furniture": (0.35, 0.10), "console": (0.18, 0.10), "other": (0.25, 0.14)}
_COND = {"like_new": 1.0, "good": 0.92, "fair": 0.80, "poor": 0.60}


def used_price(new_price: float, age_months: float, condition: str = "good", category: str = "other") -> dict:
    p = _n(new_price)
    if p <= 0: raise ValueError("price must be positive")
    first, later = _DEPR.get(category, _DEPR["other"]); age = _clamp(_n(age_months), 0, 240) / 12
    f = (1 - first) * (1 - later) ** max(0.0, age - 1) if age >= 1 else 1 - first * age
    mid = p * max(0.05, f) * _COND.get(condition, 0.92)
    return {"fair": round(mid, -1), "low": round(mid * 0.92, -1), "high": round(mid * 1.08, -1), "pct_of_new": round(mid / p * 100), "note": "הערכה לפי עקומת פחת טיפוסית. דגם נדיר או מבצע חדש משנים את התמונה."}


# ================================================================== analysis
_FRAUD = [  # code, weight, pattern, hebrew explanation
    ("advance", 28, r"מקדמה|תשלום מראש|להעביר\s+כסף|העברה\s+(?:בנקאית\s+)?לפני|advance\s+payment|deposit\s+before|pay\s+(?:first|upfront)|wire\s+(?:the\s+)?(?:money|deposit)", "מבקשים כסף לפני שראית את הנכס"),
    ("giftcard", 30, r"western\s*union|moneygram|gift\s*card|גיפט\s*קארד|כרטיס\s+מתנה|ביטקוין|bitcoin|usdt|crypto|קריפטו|bit\b", "תשלום בדרך שלא ניתן להחזיר"),
    ("abroad", 22, r"אני\s+(?:כרגע\s+)?(?:נמצא|גר|שוהה)?\s*בחו[\"״]?ל|מחוץ\s+לארץ|שולח\w*\s+(?:את\s+)?(?:המפתחות|מפתח)|i\s*(?:am|'m)\s+(?:currently\s+)?(?:abroad|overseas|out\s+of\s+(?:the\s+)?country)|keys?\s+(?:by|via)\s+(?:courier|mail|post)", "הבעלים לא בארץ ולא ניתן לראות את הנכס"),
    ("urgent", 12, r"דחוף\s+מאוד|רק\s+היום|הזדמנות\s+חד\s*פעמית|מחיר\s+מבצע\s+חד|last\s+chance|today\s+only|must\s+sell\s+today|first\s+to\s+pay", "לחץ זמן מלאכותי"),
    ("offplatform", 14, r"רק\s+(?:ב)?(?:וואטסאפ|ווטסאפ|טלגרם|whatsapp|telegram)|אל\s+תתקשר|לא\s+עונה\s+לטלפון|text\s+only|whatsapp\s+only|contact\s+only\s+by", "מסרבים לשיחה קולית"),
    ("idrequest", 24, r"צילום\s+(?:של\s+)?(?:תעודת\s+זהות|ת[\"״]?ז|רישיון)|תעודת\s+זהות\s+שלך|send\s+(?:me\s+)?(?:a\s+)?(?:copy\s+of\s+)?(?:your\s+)?(?:id|passport|license)", "מבקשים מסמכי זהות לפני כל דבר אחר"),
    ("shortlink", 10, r"bit\.ly|tinyurl|t\.co/|cutt\.ly|rb\.gy|goo\.gl|is\.gd", "קישור מקוצר שמסתיר לאן הוא מוביל"),
    ("shouting", 6, r"!{4,}|\${2,}|[A-Z]{12,}", "סימני קריאה או אותיות גדולות בהגזמה"),
    ("freeinfo", 12, r"בלי\s+(?:חוזה|ערבויות|ערב|בדיקות)|ללא\s+(?:חוזה|צ[׳']?קים|ערבות)|no\s+(?:contract|credit\s+check|references)", "ויתור על חוזה או ערבויות, שני הצדדים נחשפים"),
]


def fraud_signals(text: str, ex: dict | None = None, verdict: str | None = None, gap_pct: float | None = None) -> dict:
    """Indicator only, never proof. Score 0-100, grouped level, every signal explained so the user can judge."""
    t = text or ""; ex = ex or {}; sig = []; score = 0
    for code, w, pat, why in _FRAUD:
        if re.search(pat, t, re.I): sig.append({"code": code, "weight": w, "why": why}); score += w
    if verdict == "suspicious_low" or (gap_pct is not None and gap_pct <= -35):
        sig.append({"code": "toolow", "weight": 26, "why": "מחיר נמוך בהרבה מהשוק"}); score += 26
    elif gap_pct is not None and gap_pct <= -20: sig.append({"code": "low", "weight": 10, "why": "מחיר נמוך משמעותית מהשוק"}); score += 10
    if not re.search(r"0\d{1,2}[-\s]?\d{3}[-\s]?\d{4}|\+972|\b\d{9,10}\b", t) and not ex.get("contact"): sig.append({"code": "nophone", "weight": 8, "why": "אין מספר טלפון במודעה"}); score += 8
    if ex.get("price") is None: sig.append({"code": "noprice", "weight": 5, "why": "אין מחיר מפורש"}); score += 5
    if len((t or "").split()) < 12: sig.append({"code": "thin", "weight": 6, "why": "מעט מאוד פרטים"}); score += 6
    score = int(_clamp(score, 0, 100)); level = "high" if score >= 55 else "medium" if score >= 25 else "low"
    advice = {"high": ["אל תעביר כסף ואל תשלח מסמכים לפני שראית את הנכס ופגשת את הבעלים.", "בקש שיחת וידאו חיה מהנכס ובדוק בעלות בטאבו או ברישיון הרכב."],
              "medium": ["אמת את הפרטים בשיחה קולית לפני שמתקדמים.", "השווה את המחיר למודעות דומות ובקש תמונות נוספות."],
              "low": ["לא זוהו דפוסי הונאה בולטים. עדיין: מפגשים ותשלומים רק פנים אל פנים."]}[level]
    return {"risk": score, "level": level, "level_he": {"high": "גבוה", "medium": "בינוני", "low": "נמוך"}[level], "signals": sorted(sig, key=lambda s: -s["weight"]), "advice": advice, "disclaimer": "אינדיקציה בלבד, לא הוכחה."}


def fair_price(ex: dict, comps: list[float], comps_sqm: list[float] | None = None) -> dict:
    p = ex.get("price"); area = ex.get("area_sqm"); out = {"price": p, "n": len(comps), "enough_data": len(comps) >= 5}
    if len(comps) >= 5:
        s = sorted(comps); q = lambda x: s[int((len(s) - 1) * x)]
        out.update(fair_low=round(q(0.25)), fair_mid=round(statistics.median(s)), fair_high=round(q(0.75)))
        if p: out["gap_pct"] = round((p - out["fair_mid"]) / out["fair_mid"] * 100); out["position"] = "מתחת לטווח" if p < out["fair_low"] else "בתוך הטווח" if p <= out["fair_high"] else "מעל הטווח"
    if p and area: out["price_per_sqm"] = round(p / area)
    sq = sorted(x for x in (comps_sqm or []) if x and x > 0)
    if len(sq) >= 5:
        med = statistics.median(sq); out["market_sqm"] = round(med)
        if out.get("price_per_sqm"): out["sqm_gap_pct"] = round((out["price_per_sqm"] - med) / med * 100)
        if area and not out.get("fair_mid"): out["fair_mid"] = round(med * area)
    if not out["enough_data"] and "market_sqm" not in out: out["note"] = f"צריך לפחות 5 מודעות דומות (יש {len(comps)}). הוסף עוד מודעות לאזור כדי לקבל טווח."
    return out


_OFFER = {"he": ("שלום,\nראיתי את המודעה ואני רציני בקשר. לאחר בדיקה של מחירי שוק דומים, אני מוכן להציע {open}. אם זה מתאים, אפשר לסגור במהירות ובלי תיווך מיותר. מתי נוח לך לדבר?",
                 "מבין שהמחיר המבוקש {ask}. בהתחשב ב{lever}, אוכל להגיע עד {target}. זו הצעה אמיתית ואני זמין לסגור השבוע."),
          "en": ("Hello, I'm serious about the listing. Based on comparable prices I can offer {open}. If that works we can move quickly. When can we talk?",
                 "I understand you're asking {ask}. Considering {lever}, I can go up to {target}. It's a genuine offer and I can close this week."),
          "ru": ("Здравствуйте! Я серьёзно заинтересован. С учётом цен на похожие объекты могу предложить {open}. Если подходит, можем быстро оформить. Когда удобно поговорить?",
                 "Понимаю, что вы просите {ask}. С учётом {lever} могу дойти до {target}. Это реальное предложение, готов закрыть сделку на этой неделе."),
          "ar": ("مرحباً، أنا جاد بخصوص الإعلان. بناءً على أسعار مشابهة يمكنني تقديم {open}. إذا كان مناسباً يمكننا الإنهاء بسرعة. متى يناسبك التحدث؟",
                 "أفهم أن السعر المطلوب {ask}. مع الأخذ في الاعتبار {lever} يمكنني الوصول إلى {target}. هذا عرض حقيقي ومستعد للإغلاق هذا الأسبوع.")}
_LEVER = {"he": ("כך שהעסקה סגורה מהר ובמזומן", "הצורך בשיפוץ", "הסיכונים שציינתי"), "en": ("a fast cash closing", "the renovation needed", "the points I mentioned"),
          "ru": ("быстрой сделки за наличные", "необходимости ремонта", "упомянутых мною рисков"), "ar": ("الإغلاق السريع نقداً", "الحاجة للتجديد", "النقاط التي ذكرتها")}


def negotiation(ex: dict, insight: dict | None = None, fraud: dict | None = None, lang: str = "he") -> dict:
    ex = ex or {}; ask = ex.get("price"); insight = insight or {}; lang = lang if lang in _OFFER else "he"
    if not ask: return {"enough": False, "note": "אין מחיר מפורש במודעה. שאל קודם כמה המוכר מבקש."}
    gap = insight.get("gap_pct"); v = insight.get("verdict"); mkt = (insight.get("market") or {}).get("median")
    if v == "above_market" and gap is not None: open_p = ask * (1 - _clamp(gap / 100 + 0.04, 0.08, 0.18)); tgt = max(mkt or ask * 0.92, open_p); walk = (mkt or ask) * 1.04
    elif v == "good_deal": open_p, tgt, walk = ask * 0.96, ask * 0.98, ask
    elif v == "suspicious_low": open_p = tgt = walk = ask
    else: open_p, tgt, walk = ask * 0.93, ask * 0.96, ask * 0.99
    flex = bool(ex.get("negotiable") or ex.get("urgent")); open_p *= 0.98 if flex else 1; tgt *= 0.99 if flex else 1
    levers = []
    if ex.get("urgent"): levers.append("המוכר נראה לחוץ, זה יתרון")
    if ex.get("negotiable"): levers.append("המודעה מציינת גמישות במחיר")
    if ex.get("condition") == "needs_renovation": levers.append("הנכס דורש שיפוץ, תעריך עלות ותוריד אותה מהמחיר")
    if v == "above_market": levers.append("המחיר מעל החציון של מודעות דומות, יש לך נתונים לתמוך בהצעה")
    if ex.get("broker") is False: levers.append("אין מתווך, המוכר חוסך עמלה")
    if fraud and fraud.get("level") == "high": levers.append("אזהרה: סיכון הונאה גבוה, אל תתמקד במחיר לפני שאימתת את המוכר")
    step = 100 if ask < 100000 else 1000; r = lambda x: round(x / step) * step
    open_p = r(open_p); tgt = max(r(tgt), open_p + step if v != "suspicious_low" else open_p); walk = max(r(walk), tgt)                 # keep open < target <= walk after rounding
    cur = "$" if ex.get("currency") == "USD" else ("€" if ex.get("currency") == "EUR" else "₪")
    f = lambda x: f"{cur}{x:,.0f}" if cur != "₪" else f"{x:,.0f} ₪"; lv = _LEVER[lang][1 if ex.get("condition") == "needs_renovation" else 0]
    msg = _OFFER[lang][0].format(open=f(open_p)) + "\n\n" + _OFFER[lang][1].format(ask=f(ask), lever=lv, target=f(tgt))
    return {"enough": True, "ask": ask, "open": open_p, "target": tgt, "walk_away": walk, "saving_at_target_pct": round((ask - tgt) / ask * 100, 1), "levers": levers, "message": msg, "lang": lang,
            "tips": ["פתח נמוך אבל הגיוני, ובקש מהמוכר להציע מחיר ראשון.", "אל תחשוף את התקרה שלך.", "חתום רק אחרי שראית את הנכס ובדקת בעלות."]}


_TAGS = [("parking", "חניה", r"חני(?:ה|יה)|parking|garage|מחסן\s+וחניה"), ("elevator", "מעלית", r"מעלית|elevator|lift"), ("safe_room", "ממ״ד", r"ממ[\"״']?ד|מרחב\s+מוגן|safe\s*room"),
         ("balcony", "מרפסת", r"מרפסת|balcon"), ("renovated", "משופצת", r"משופצ|שופצ|renovated|גמר\s+מעולה"), ("new", "חדשה", r"חדש(?:ה)?\s+מקבלן|מקבלן|new\s+build|פרויקט\s+חדש"),
         ("garden", "גינה", r"גינה|garden|חצר"), ("storage", "מחסן", r"מחסן|storage"), ("ac", "מיזוג", r"מיזוג|מזגן|a/?c\b|air\s*cond"), ("furnished", "מרוהטת", r"מרוהט|furnished"),
         ("pets", "חיות מותרות", r"חיות\s+מותר|pets?\s+(?:allowed|ok)"), ("roof", "גג/פנטהאוז", r"גג|פנטהאוז|penthouse|דופלקס|duplex"), ("view", "נוף", r"נוף|view"),
         ("quiet", "שקט", r"שקט|quiet"), ("train", "קרוב לרכבת/קלה", r"רכבת|train|קו\s+אדום|רכבת\s+קלה|light\s+rail"), ("nobroker", "ללא תיווך", r"ללא\s+תיווך|בלי\s+תיווך|no\s+(?:broker|agent)|ישירות\s+מבעל"),
         ("negotiable", "גמיש במחיר", r"גמיש|ניתן\s+להתמקח|negotiable|או\s+הצעה"), ("handone", "יד ראשונה", r"יד\s+ראשונה|first\s+hand|one\s+owner"), ("warranty", "באחריות", r"אחריות|warranty|guarantee"),
         ("service", "היסטוריית טיפולים", r"היסטוריית\s+טיפולים|service\s+history|טיפולי\s+מוסך"), ("test", "טסט בתוקף", r"טסט\s+(?:ל|עד|בתוקף)|טסט\b|\btest\s+valid")]


def smart_tags(text: str, ex: dict | None = None) -> list[dict]:
    ex = ex or {}; t = text or ""; out = []
    for code, he, pat in _TAGS:
        m = re.search(pat, t, re.I)
        if not m: continue
        if code in ("parking", "elevator", "balcony", "safe_room", "storage", "ac") and re.search(r"(?:ללא|בלי|אין|no|without)\s*(?:" + pat + ")", t, re.I): continue      # negated
        out.append({"code": code, "label": he})
    have = {x["code"] for x in out}
    for code, he in (("parking", "חניה"), ("elevator", "מעלית"), ("balcony", "מרפסת"), ("safe_room", "ממ״ד"), ("storage", "מחסן"), ("ac", "מיזוג"), ("garden", "גינה")):
        if code in (ex.get("features") or []) and code not in have: out.append({"code": code, "label": he})
    if ex.get("floor") is not None: out.append({"code": "floor", "label": "קרקע" if ex["floor"] == 0 else f"קומה {ex['floor']}" + (f"/{ex['total_floors']}" if ex.get("total_floors") else "")})
    if ex.get("area_sqm"): out.append({"code": "area", "label": f"{ex['area_sqm']:g} מ״ר"})
    if ex.get("rooms"): out.append({"code": "rooms", "label": f"{ex['rooms']:g} חדרים"})
    if ex.get("year"): out.append({"code": "year", "label": f"שנת {ex['year']}"})
    if ex.get("km") is not None and ex.get("category") == "vehicles": out.append({"code": "km", "label": f"{ex['km']:,} ק״מ"})
    if ex.get("hand") and ex.get("category") == "vehicles": out.append({"code": "hand", "label": f"יד {ex['hand']}"})
    seen = set(); return [x for x in out if not (x["code"] in seen or seen.add(x["code"]))]


def checklist(category: str | None, ex: dict | None = None) -> list[dict]:
    ex = ex or {}; cat = category or ex.get("category")
    if cat == "real_estate":
        g = [("שאלות למוכר", ["למה מוכרים או משכירים ומאיזה תאריך הנכס פנוי?", "מה גובה ארנונה, ועד בית ומים וחשמל ממוצע לחודש?", "האם יש שעבוד, משכנתא או עיקול על הנכס? מי רשום בטאבו?", "האם בוצעו שינויים או תוספות בנייה עם היתר?", "מה כלול במחיר (מטבח, מזגנים, ריהוט)?"]),
             ("בדיקה במקום", ["לחות, עובש או סימני נזילה בתקרה ובפינות", "לחץ מים בכל הברזים וניקוז במקלחת", "חלונות, תריסים ואיטום, בדוק גם ביום גשום", "לוח חשמל וכמה נקודות חשמל בכל חדר", "רעש מהרחוב, ריחות, שכנים, חניה בערב"]),
             ("לפני החתימה", ["נסח טאבו עדכני ואישור זכויות מהוועד", "עורך דין שבודק את החוזה, לא של המוכר", "בדיקת מהנדס או שמאי בקנייה", "בשכירות: ערבות, צ׳קים ותנאי יציאה מוקדמת"])]
        if ex.get("condition") == "needs_renovation": g[1][1].append("הצעת מחיר ממבצע שיפוץ לפני שמחליטים על מחיר")
        return [{"title": a, "items": b} for a, b in g]
    if cat == "vehicles":
        return [{"title": "שאלות למוכר", "items": ["כמה ידיים והאם הרכב על שמך? יש בעלות פרטית?", "האם יש היסטוריית טיפולים מלאה ומסמכים?", "תאונות או שינויים? למה מוכר?", "מתי הטסט ואם עבר, מה היה בדוח?"]},
                {"title": "בדיקה במקום", "items": ["מנוע קר: התנעה, עשן, רעשים", "צמיגים, בלמים והגה, נסיעת מבחן ארוכה", "סימני צבע ותיקוני פח, מרווחים בין הדלתות", "נורות אזהרה בלוח, מזגן, חלונות חשמל"]},
                {"title": "לפני התשלום", "items": ["בדיקה במכון בדיקה מורשה", "בדיקת היסטוריה ברשות הרישוי ועיקולים", "העברת בעלות במקום ולא אחר כך", "תשלום רק בהעברה בנקאית או צ׳ק בנקאי מאובטח"]}]
    return [{"title": "שאלות למוכר", "items": ["מה גיל המוצר והאם יש חשבונית?", "האם הוא באחריות ועד מתי?", "למה מוכרים ויש תקלות ידועות?", "מה כלול (מטען, קופסה, אביזרים)?"]},
            {"title": "בדיקה במקום", "items": ["הפעל אותו ובדוק כל כפתור וחיבור", "בדוק מספר סידורי מול האתר של היצרן", "בטלפונים: נעילת חשבון, iCloud/Google ובריאות סוללה", "בדוק שאינו נעול לספק או מדווח כגנוב"]},
            {"title": "לפני התשלום", "items": ["פגישה במקום ציבורי ובשעות היום", "תשלום רק אחרי בדיקה, בלי מקדמות", "קבל חשבונית או אישור מכירה בכתב"]}]


DEFAULT_WEIGHTS = {"score": 30, "price": 25, "sqm": 15, "rooms": 10, "risk": 15, "extras": 5}


def compare(rows: list[dict], weights: dict | None = None) -> dict:
    """rows: [{id, title, score, price, area, rooms, risks (int), tags (int)}]. Min-max normalised, weighted; winner and a reason per row."""
    if len(rows) < 2: raise ValueError("need at least two listings")
    w = {**DEFAULT_WEIGHTS, **{k: _clamp(_n(v), 0, 100) for k, v in (weights or {}).items() if k in DEFAULT_WEIGHTS}}
    def norm(key, higher_better=True, derive=None):
        vals = [derive(r) if derive else r.get(key) for r in rows]; ok = [v for v in vals if v is not None]
        if not ok or max(ok) == min(ok): return [0.5 if v is not None else 0.3 for v in vals]
        lo, hi = min(ok), max(ok); return [(((v - lo) / (hi - lo)) if higher_better else 1 - (v - lo) / (hi - lo)) if v is not None else 0.3 for v in vals]
    cols = {"score": norm("score"), "price": norm("price", False), "sqm": norm(None, False, lambda r: (r["price"] / r["area"]) if r.get("price") and r.get("area") else None),
            "rooms": norm("rooms"), "risk": norm("risks", False), "extras": norm("tags")}
    tot = sum(w.values()) or 1; out = []
    for i, r in enumerate(rows):
        sc = sum(w[k] * cols[k][i] for k in w) / tot * 100; best = sorted(w, key=lambda k: -(w[k] * cols[k][i]))[:2]
        he = {"score": "ציון התאמה גבוה", "price": "המחיר הנמוך", "sqm": "מחיר למ״ר טוב", "rooms": "יותר חדרים", "risk": "מעט סיכונים", "extras": "הרבה מאפיינים"}
        out.append({**r, "total": round(sc), "why": " · ".join(he[k] for k in best if cols[k][i] >= 0.6) or "מאוזן"})
    out.sort(key=lambda r: -r["total"]); return {"ranking": out, "winner": out[0].get("id"), "weights": w}


def clusters(items: list[dict], cos: float = 0.88) -> list[dict]:
    """items: [{id, text, price, score, city, rooms, area, source}]. Same property listed twice: very similar text, or same city+rooms with price within 3%."""
    emb = [neardup.embed(i.get("text") or "") for i in items]; par = list(range(len(items)))
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            A, B = items[a], items[b]; same = neardup.cosine(emb[a], emb[b]) >= cos
            if not same and A.get("city") and A.get("city") == B.get("city") and A.get("rooms") and A.get("rooms") == B.get("rooms") and A.get("price") and B.get("price"):
                close = abs(A["price"] - B["price"]) / max(A["price"], B["price"]) <= 0.03
                same = close and (not (A.get("area") and B.get("area")) or abs(A["area"] - B["area"]) / max(A["area"], B["area"]) <= 0.05)
            if same: par[find(a)] = find(b)
    groups: dict[int, list] = {}
    for i, it in enumerate(items): groups.setdefault(find(i), []).append(it)
    out = []
    for g in groups.values():
        if len(g) < 2: continue
        priced = [x for x in g if x.get("price")]; cheapest = min(priced, key=lambda x: x["price"]) if priced else None; best = max(g, key=lambda x: x.get("score") or 0)
        out.append({"count": len(g), "ids": [x["id"] for x in g], "cheapest": cheapest["id"] if cheapest else None, "best_score": best["id"],
                    "price_spread": round(max(x["price"] for x in priced) - min(x["price"] for x in priced)) if len(priced) > 1 else 0})
    return sorted(out, key=lambda g: -g["count"])


# ================================================================== multi-language messages
LANGS = {"he": "עברית", "en": "English", "ru": "Русский", "ar": "العربية"}
KINDS = {"first": "פנייה ראשונה", "followup": "מעקב", "offer": "הצעת מחיר", "visit": "תיאום צפייה", "thanks": "תודה ודחייה מנומסת"}
_MSG = {
    "he": {"first": "שלום, ראיתי את המודעה על {thing}{pr}. האם עדיין זמין? אשמח לפרטים ולתאם צפייה.", "followup": "שלום, חוזר בנוגע ל{thing}. האם עדיין רלוונטי? אשמח לתאם שיחה או צפייה השבוע.",
           "offer": "שלום, מעוניין ב{thing}. אני מוכן להציע {offer}. אפשר לסגור מהר אם זה מתאים. מה דעתך?", "visit": "שלום, אשמח לראות את {thing}. מתאים לך {slot}? אפשר להציע זמן אחר.",
           "thanks": "תודה רבה על הזמן ועל הפרטים לגבי {thing}. החלטתי לא להתקדם הפעם. בהצלחה במכירה!", "greet": "שלום רב,\n", "bye": "\nבברכה,"},
    "en": {"first": "Hello, I saw your listing for {thing}{pr}. Is it still available? I'd appreciate the details and a viewing.", "followup": "Hello, following up about {thing}. Is it still available? I'd be glad to talk or view it this week.",
           "offer": "Hello, I'm interested in {thing}. I can offer {offer}. We can close quickly if that works. What do you think?", "visit": "Hello, I'd like to see {thing}. Would {slot} work? Happy to suggest another time.",
           "thanks": "Thank you for your time and the details about {thing}. I've decided not to proceed this time. Good luck with the sale!", "greet": "Dear Sir or Madam,\n", "bye": "\nKind regards,"},
    "ru": {"first": "Здравствуйте! Увидел ваше объявление: {thing}{pr}. Оно ещё актуально? Буду рад деталям и возможности посмотреть.", "followup": "Здравствуйте! Пишу снова по поводу: {thing}. Ещё актуально? Готов поговорить или посмотреть на этой неделе.",
           "offer": "Здравствуйте! Меня интересует: {thing}. Готов предложить {offer}. Можем быстро оформить, если подходит. Что скажете?", "visit": "Здравствуйте! Хотел бы посмотреть: {thing}. Вам подойдёт {slot}? Могу предложить другое время.",
           "thanks": "Спасибо за время и информацию по {thing}. В этот раз я решил не продолжать. Удачной продажи!", "greet": "Добрый день,\n", "bye": "\nС уважением,"},
    "ar": {"first": "مرحباً، رأيت إعلانكم عن {thing}{pr}. هل ما زال متاحاً؟ أود معرفة التفاصيل وترتيب معاينة.", "followup": "مرحباً، أتابع بخصوص {thing}. هل ما زال متاحاً؟ يسعدني التحدث أو المعاينة هذا الأسبوع.",
           "offer": "مرحباً، أنا مهتم بـ {thing}. يمكنني تقديم {offer}. نستطيع الإنهاء بسرعة إذا كان مناسباً. ما رأيكم؟", "visit": "مرحباً، أود معاينة {thing}. هل يناسبكم {slot}؟ يمكنني اقتراح وقت آخر.",
           "thanks": "شكراً لوقتكم والمعلومات عن {thing}. قررت عدم المتابعة هذه المرة. بالتوفيق في البيع!", "greet": "تحية طيبة،\n", "bye": "\nمع التقدير،"}}


def _city(ex: dict, lang: str) -> str:
    loc = ex.get("location") or ""
    if lang == "he" and loc:
        try:
            from .feeds import hebrew_name
            return hebrew_name(loc) or loc
        except Exception: return loc
    return loc


def _thing(ex: dict, lang: str) -> str:
    cat = ex.get("category"); city = _city(ex, lang); r = ex.get("rooms")
    if cat == "real_estate":
        base = {"he": f"דירת {r:g} חדרים" if r else "הדירה", "en": f"the {r:g}-room apartment" if r else "the apartment", "ru": f"квартира {r:g} комн." if r else "квартира", "ar": f"شقة {r:g} غرف" if r else "الشقة"}[lang]
        return base + ((" " + {"he": "ב", "en": "in ", "ru": "в ", "ar": "في "}[lang] + city) if city else "")
    if cat in ("vehicles", "electronics"):
        nm = " ".join(str(x) for x in (ex.get("brand"), ex.get("model"), ex.get("year") if cat == "vehicles" else None) if x)
        return nm or {"he": "הרכב" if cat == "vehicles" else "המוצר", "en": "the vehicle" if cat == "vehicles" else "the item", "ru": "автомобиль" if cat == "vehicles" else "товар", "ar": "السيارة" if cat == "vehicles" else "المنتج"}[lang]
    return {"he": "הפריט", "en": "the item", "ru": "товар", "ar": "العنصر"}[lang]


def _money(x, cur="ILS"):
    sym = {"ILS": "₪", "USD": "$", "EUR": "€"}.get(cur or "ILS", "₪"); return f"{x:,.0f} ₪" if sym == "₪" else f"{sym}{x:,.0f}"


def message(kind: str, lang: str, ex: dict | None = None, tone: str = "friendly", name: str = "", offer: float | None = None, slot: str = "") -> str:
    ex = ex or {}; lang = lang if lang in _MSG else "he"; kind = kind if kind in KINDS else "first"; m = _MSG[lang]
    pr = f" ({_money(ex['price'], ex.get('currency'))})" if ex.get("price") and kind in ("first", "followup") else ""
    body = m[kind].format(thing=_thing(ex, lang), pr=pr, offer=_money(offer, ex.get("currency")) if offer else "...", slot=slot or {"he": "מחר", "en": "tomorrow", "ru": "завтра", "ar": "غداً"}[lang])
    if tone == "short": body = body.split(". ")[0].rstrip(".") + "."
    elif tone == "formal": body = m["greet"] + body + m["bye"]
    sign = (name or "").strip()[:40]; return body + (("\n" if tone != "formal" else " ") + sign if sign else "")


# ================================================================== CRM, reminders, rules, clients
STAGES = [("new", "חדש"), ("contacted", "נוצר קשר"), ("viewing", "צפייה"), ("negotiating", "משא ומתן"), ("won", "נסגר"), ("lost", "לא רלוונטי")]
STAGE_IDS = [s for s, _ in STAGES]
MAX_CRM, MAX_NOTES = 500, 20


def crm_update(crm: dict, lid: str, stage: str | None = None, note: str | None = None, due: str | None = None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.utcnow(); crm = dict(crm or {}); e = dict(crm.get(lid) or {"stage": "new", "notes": [], "due": None, "created": now.isoformat(timespec="seconds")})
    if stage is not None:
        if stage not in STAGE_IDS: raise ValueError("unknown stage")
        e["stage"] = stage
    if note:
        e["notes"] = ([{"t": now.isoformat(timespec="seconds"), "text": note.strip()[:500]}] + list(e.get("notes") or []))[:MAX_NOTES]
    if due is not None:
        if due == "": e["due"] = None; e["notified"] = False
        else:
            try: dt.date.fromisoformat(due[:10])
            except ValueError: raise ValueError("due must be YYYY-MM-DD")
            e["due"] = due[:10]; e["notified"] = False
    e["updated"] = now.isoformat(timespec="seconds"); crm[lid] = e
    if len(crm) > MAX_CRM:                                    # drop the least recently updated closed entries first
        for k, _ in sorted(crm.items(), key=lambda kv: (kv[1].get("stage") not in ("won", "lost"), kv[1].get("updated", "")))[:len(crm) - MAX_CRM]: crm.pop(k, None)
    return crm


def due_reminders(crm: dict, today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today(); out = []
    for lid, e in (crm or {}).items():
        if e.get("due") and e.get("stage") not in ("won", "lost"):
            try: d = dt.date.fromisoformat(e["due"])
            except ValueError: continue
            out.append({"listing_id": lid, "due": e["due"], "overdue": d < today, "today": d == today, "days": (d - today).days, "stage": e.get("stage"), "last_note": (e.get("notes") or [{}])[0].get("text")})
    return sorted(out, key=lambda r: r["days"])


MAX_RULES = {"starter": 2, "pro": 10, "vip": 40}


def validate_rule(d: dict) -> dict:
    name = str(d.get("name") or "כלל").strip()[:60] or "כלל"; num = lambda k: (_n(d.get(k)) if d.get(k) not in (None, "") else None)
    kw = lambda k: [str(x).strip()[:40] for x in (d.get(k) or []) if str(x).strip()][:10]
    cat = d.get("category") or None
    if cat not in (None, "real_estate", "vehicles", "electronics", "furniture"): raise ValueError("bad category")
    r = {"id": str(d.get("id") or "")[:36], "name": name, "active": bool(d.get("active", True)), "category": cat, "city": (str(d.get("city") or "").strip()[:60] or None), "min_score": int(_clamp(_n(d.get("min_score"), 0), 0, 100)),
         "min_price": num("min_price"), "max_price": num("max_price"), "rooms_min": num("rooms_min"), "rooms_max": num("rooms_max"), "keywords": kw("keywords"), "exclude": kw("exclude"),
         "verdict": d.get("verdict") if d.get("verdict") in ("good_deal", "fair", "any", None) else None}
    if r["min_price"] is not None and r["max_price"] is not None and r["min_price"] > r["max_price"]: raise ValueError("min_price is above max_price")
    return r


def rule_match(rule: dict, row: dict) -> bool:
    """row: {score, extracted, text, verdict?}. All given conditions must hold."""
    if not rule.get("active", True): return False
    ex = row.get("extracted") or {}; t = (row.get("text") or "").lower()
    if rule.get("category") and ex.get("category") != rule["category"]: return False
    if rule.get("city") and rule["city"].lower() not in (str(ex.get("location") or "") + " " + t).lower(): return False
    if (row.get("score") or 0) < (rule.get("min_score") or 0): return False
    p = ex.get("price")
    if rule.get("max_price") is not None and (p is None or p > rule["max_price"]): return False
    if rule.get("min_price") is not None and (p is None or p < rule["min_price"]): return False
    r = ex.get("rooms")
    if rule.get("rooms_min") is not None and (r is None or r < rule["rooms_min"]): return False
    if rule.get("rooms_max") is not None and (r is None or r > rule["rooms_max"]): return False
    if any(k.lower() in t for k in rule.get("exclude") or []): return False
    if rule.get("keywords") and not all(k.lower() in t for k in rule["keywords"]): return False
    if rule.get("verdict") == "good_deal" and row.get("verdict") != "good_deal": return False
    return True


def validate_client(d: dict) -> dict:
    num = lambda k: (_n(d.get(k)) if d.get(k) not in (None, "") else None)
    c = {"id": str(d.get("id") or "")[:36], "name": str(d.get("name") or "").strip()[:80], "phone": re.sub(r"[^\d+\-\s]", "", str(d.get("phone") or ""))[:20], "category": d.get("category") or "real_estate",
         "budget_min": num("budget_min"), "budget_max": num("budget_max"), "cities": [str(x).strip()[:40] for x in (d.get("cities") or []) if str(x).strip()][:6],
         "rooms_min": num("rooms_min"), "rooms_max": num("rooms_max"), "must": [str(x).strip()[:30] for x in (d.get("must") or []) if str(x).strip()][:8], "notes": str(d.get("notes") or "")[:400]}
    if not c["name"]: raise ValueError("client name is required")
    if c["category"] not in ("real_estate", "vehicles", "electronics", "furniture"): raise ValueError("bad category")
    return c


def match_client(client: dict, ex: dict, score: int = 0, tags: list[str] | None = None) -> dict:
    fit = 0.0; why = []; bad = []; p = ex.get("price")
    if ex.get("category") and client.get("category") and ex["category"] != client["category"]: return {"fit": 0, "reasons": [], "blockers": ["קטגוריה אחרת"]}
    if p is None: fit += 15; why.append("אין מחיר, צריך לברר")
    else:
        mx, mn = client.get("budget_max"), client.get("budget_min")
        if mx and p > mx * 1.10: bad.append(f"מעל התקציב ב-{round((p / mx - 1) * 100)}%")
        elif mx and p > mx: fit += 12; why.append("מעט מעל התקציב, אפשר לנהל משא ומתן")
        elif mn and p < mn * 0.7: fit += 20; why.append("זול בהרבה מהתקציב, לבדוק למה")
        else: fit += 35; why.append("בתוך התקציב")
    cities = [c.lower() for c in client.get("cities") or []]
    if not cities: fit += 25
    elif str(ex.get("location") or "").lower() in cities or any(c in str(ex.get("location") or "").lower() for c in cities): fit += 25; why.append("באזור המבוקש")
    else: bad.append("מחוץ לאזור")
    r = ex.get("rooms"); rmin, rmax = client.get("rooms_min"), client.get("rooms_max")
    if rmin is None and rmax is None: fit += 20
    elif r is None: fit += 8
    elif (rmin is None or r >= rmin) and (rmax is None or r <= rmax): fit += 20; why.append(f"{r:g} חדרים")
    else: bad.append("מספר חדרים לא מתאים")
    must = [m.lower() for m in client.get("must") or []]; have = [t.lower() for t in (tags or [])]
    if must:
        got = [m for m in must if any(m in h or h in m for h in have)]; fit += 15 * len(got) / len(must)
        if len(got) < len(must): bad.append("חסר: " + ", ".join(m for m in must if m not in got))
        else: why.append("יש את כל הדרישות")
    else: fit += 15
    fit += 5 * _clamp(score, 0, 100) / 100
    return {"fit": int(_clamp(fit, 0, 100)) if not any(b.startswith("מעל התקציב") or b == "מחוץ לאזור" or b.startswith("מספר חדרים") for b in bad) else int(min(fit, 40)), "reasons": why, "blockers": bad}


# ================================================================== reports, share, sheet, csv, paste
def market_report(rows: list[dict], category: str = "real_estate", location: str | None = None) -> dict:
    """rows: [{location, rooms, price, area, created (datetime|None)}]."""
    from . import market
    rs = [r for r in rows if r.get("price") and (not location or str(r.get("location") or "").lower() == location.lower())]
    out = {"category": category, "location": location, "n": len(rs), "overall": market.summarize([r["price"] for r in rs]), "by_rooms": [], "by_city": [], "cheapest": [], "trend": []}
    for key, label in (("rooms", "by_rooms"), ("location", "by_city")):
        g: dict = {}
        for r in rs:
            if r.get(key) is not None: g.setdefault(r[key], []).append(r["price"])
        out[label] = sorted([{"key": k, **market.summarize(v)} for k, v in g.items() if len(v) >= 3], key=lambda x: (-(x.get("n") or 0)))[:12]
    sqm = [r["price"] / r["area"] for r in rs if r.get("area")]
    if len(sqm) >= 3: out["sqm"] = {"median": round(statistics.median(sqm)), "min": round(min(sqm)), "max": round(max(sqm)), "n": len(sqm)}
    med = out["overall"].get("median")
    if med: out["cheapest"] = [{**{k: r.get(k) for k in ("id", "location", "rooms", "price", "area")}, "below_median_pct": round((1 - r["price"] / med) * 100)} for r in sorted(rs, key=lambda r: r["price"])[:5] if r["price"] < med]
    pts = [(r["created"], r["price"]) for r in rs if isinstance(r.get("created"), dt.datetime)]
    out["trend"] = market.weekly_trend(pts)[-8:] if pts else []
    if len(out["trend"]) >= 2 and out["trend"][-2]["median"]:
        d = (out["trend"][-1]["median"] - out["trend"][-2]["median"]) / out["trend"][-2]["median"] * 100; out["trend_pct"] = round(d, 1); out["trend_he"] = "עלייה" if d > 1 else "ירידה" if d < -1 else "יציבות"
    return out


def brand_clean(b: dict | None) -> dict:
    b = b or {}; col = str(b.get("color") or "#1f6feb")
    return {"name": str(b.get("name") or "Smart Sniper AI").strip()[:60], "phone": re.sub(r"[^\d+\-\s]", "", str(b.get("phone") or ""))[:20], "email": str(b.get("email") or "").strip()[:80] if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(b.get("email") or "").strip()) else "",
            "tagline": str(b.get("tagline") or "").strip()[:100], "color": col if re.fullmatch(r"#[0-9a-fA-F]{6}", col) else "#1f6feb"}


def _line(row: dict) -> str:
    ex = row.get("extracted") or {}; bits = [ex.get("location") or "", f"{ex['rooms']:g} חד׳" if ex.get("rooms") else "", f"{ex['area_sqm']:g} מ״ר" if ex.get("area_sqm") else "", _money(ex["price"], ex.get("currency")) if ex.get("price") else ""]
    return " | ".join(b for b in bits if b)


def share_texts(row: dict, brand: dict | None = None, insight: dict | None = None) -> dict:
    b = brand_clean(brand); ex = row.get("extracted") or {}; head = f"🏠 {_line(row)}" if ex.get("category") == "real_estate" else f"⭐ {_line(row)}"
    v = {"good_deal": "מחיר טוב מהשוק", "fair": "מחיר הוגן", "above_market": "מעל השוק", "suspicious_low": "מחיר חשוד, לאמת"}.get((insight or {}).get("verdict"), "")
    lines = [head, f"התאמה: {row.get('score', 0)}%" + (f" · {v}" if v else "")]
    for r in (row.get("risks") or [])[:2]: lines.append("⚠️ " + str(r)[:90])
    if row.get("source_url"): lines.append(row["source_url"])
    foot = b["name"] + (f" · {b['phone']}" if b["phone"] else ""); wa = "\n".join(lines + ["", foot]).strip()
    return {"whatsapp": wa, "telegram": wa.replace("🏠", "🏠").replace("⭐", "⭐"), "email": {"subject": f"הזדמנות: {_line(row)}"[:120], "body": "שלום,\n\nמצאתי נכס שעשוי להתאים לך:\n\n" + "\n".join(lines) + f"\n\nבברכה,\n{b['name']}" + (f"\n{b['phone']}" if b["phone"] else "")}}


def weekly_brief(rows: list[dict], days: int = 7, brand: dict | None = None) -> tuple[str, str]:
    """rows: [{score, extracted, status, verdict?, created}] already limited to the period."""
    b = brand_clean(brand); good = [r for r in rows if r.get("status") in ("new", "saved") and (r.get("score") or 0) >= 70]; top = sorted(good, key=lambda r: -(r.get("score") or 0))[:5]
    prices = [r["extracted"]["price"] for r in rows if (r.get("extracted") or {}).get("price")]
    subj = f"{b['name']}: {len(good)} הזדמנויות חזקות ב-{days} הימים האחרונים" if good else f"{b['name']}: תקציר שבועי"
    lines = [f"סה״כ נסרקו {len(rows)} מודעות, מתוכן {len(good)} עם התאמה של 70% ומעלה." + (f" מחיר חציוני: {_money(statistics.median(prices))}." if len(prices) >= 3 else ""), ""]
    for i, r in enumerate(top, 1): lines.append(f"{i}. {r.get('score')}% · {_line(r)}" + (" · מחיר טוב" if r.get("verdict") == "good_deal" else ""))
    if not top: lines.append("אין השבוע הזדמנויות חזקות. מומלץ להרחיב את האזור או התקציב.")
    return subj, "\n".join(lines + ["", b["name"] + (f" · {b['phone']}" if b["phone"] else "")])


def deal_sheet_html(row: dict, insight: dict | None, fraud: dict | None, tags: list[dict], brand: dict | None = None, ai_notes: list[str] | None = None) -> str:
    e = lambda s: _html.escape(str(s if s is not None else ""), quote=True); b = brand_clean(brand); ex = row.get("extracted") or {}; v = insight or {}; f = fraud or {}
    verdict = {"good_deal": "מחיר טוב מהשוק", "fair": "מחיר הוגן", "above_market": "מעל מחיר השוק", "suspicious_low": "מחיר חשוד, נדרש אימות", "unknown": "אין מספיק נתוני שוק"}.get(v.get("verdict"), "")
    kv = [("מיקום", ex.get("location")), ("חדרים", ex.get("rooms")), ("שטח", f"{ex['area_sqm']:g} מ״ר" if ex.get("area_sqm") else None), ("קומה", ex.get("floor")), ("מחיר", _money(ex["price"], ex.get("currency")) if ex.get("price") else None),
          ("מחיר למ״ר", _money(ex["price_per_sqm"]) if ex.get("price_per_sqm") else None), ("מצב", ex.get("condition")), ("שנה", ex.get("year")), ("קילומטראז׳", f"{ex['km']:,}" if ex.get("km") else None)]
    rows = "".join(f"<tr><th>{e(k)}</th><td>{e(x)}</td></tr>" for k, x in kv if x not in (None, "", 0))
    chips = "".join(f"<span class=chip>{e(t['label'])}</span>" for t in tags[:14]); risks = "".join(f"<li>{e(r)}</li>" for r in (row.get("risks") or [])[:6])
    notes = "".join(f"<li>{e(n)}</li>" for n in (ai_notes or [])[:6]); src = f"<p class=src>מקור: <a href='{e(row['source_url'])}' rel='noopener nofollow'>{e(row['source_url'])}</a></p>" if str(row.get("source_url") or "").startswith(("http://", "https://")) else ""
    risk_lvl = f"<div class='risk r-{e(f.get('level', 'low'))}'>סיכון הונאה: {e(f.get('level_he', 'נמוך'))} ({e(f.get('risk', 0))}/100)</div>" if f else ""
    return f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(_line(row) or 'דף עסקה')}</title>
<style>:root{{--c:{b['color']}}}*{{box-sizing:border-box}}body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6fb;color:#16202e}}.page{{max-width:760px;margin:24px auto;background:#fff;border-radius:18px;box-shadow:0 10px 40px #0001;overflow:hidden;animation:up .6s ease both}}
@keyframes up{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}header{{background:linear-gradient(135deg,var(--c),#0b1d3a);color:#fff;padding:26px 28px}}header h1{{margin:0 0 4px;font-size:22px}}header p{{margin:0;opacity:.85}}
.score{{float:left;width:84px;height:84px;border-radius:50%;background:conic-gradient(#fff {int(row.get('score', 0))}%,#ffffff33 0);display:grid;place-items:center}}.score b{{width:66px;height:66px;border-radius:50%;background:var(--c);display:grid;place-items:center;font-size:22px}}
main{{padding:22px 28px}}h2{{font-size:15px;margin:22px 0 8px;color:var(--c)}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:right;padding:8px 6px;border-bottom:1px solid #eef1f6;font-size:14px}}th{{color:#667}}.chip{{display:inline-block;margin:3px;padding:4px 10px;border-radius:99px;background:#eaf1ff;color:var(--c);font-size:12px}}
.verdict{{padding:12px 14px;border-radius:12px;background:#f1f7ee;border:1px solid #cfe5c7;font-weight:600}}.risk{{margin-top:10px;padding:10px 14px;border-radius:12px;font-weight:600;background:#eef6ee}}.r-medium{{background:#fff6e0}}.r-high{{background:#fde8e8}}
ul{{margin:6px 0;padding-inline-start:20px;font-size:14px}}footer{{padding:16px 28px;background:#f8f9fc;font-size:13px;color:#556;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}.src{{font-size:12px;color:#778;word-break:break-all}}
@media print{{body{{background:#fff}}.page{{box-shadow:none;margin:0;animation:none}}}}</style></head><body><div class="page"><header><div class="score"><b>{e(row.get('score', 0))}</b></div><h1>{e(_line(row) or 'הזדמנות')}</h1><p>{e(b['tagline'] or 'ניתוח הזדמנות מבוסס נתונים')}</p></header>
<main>{('<div class=verdict>' + e(verdict) + (f" ({e(v.get('reason'))})" if v.get('reason') else '') + '</div>') if verdict else ''}{risk_lvl}<h2>פרטים</h2><table>{rows}</table><h2>מאפיינים</h2><div>{chips or '—'}</div>
{('<h2>נקודות לתשומת לב</h2><ul>' + risks + '</ul>') if risks else ''}{('<h2>תובנות</h2><ul>' + notes + '</ul>') if notes else ''}{src}</main>
<footer><b>{e(b['name'])}</b><span>{e(b['phone'])} {e(b['email'])}</span><span>הנתונים הם הערכה ואינם ייעוץ משפטי או פיננסי.</span></footer></div></body></html>"""


_CSV_COLS = [("score", "ציון"), ("status", "סטטוס"), ("category", "קטגוריה"), ("location", "מיקום"), ("rooms", "חדרים"), ("area_sqm", "מ״ר"), ("price", "מחיר"), ("price_per_sqm", "מחיר למ״ר"), ("condition", "מצב"), ("broker", "מתווך"),
             ("stage", "שלב CRM"), ("created", "נוצר"), ("source_url", "קישור"), ("risks", "סיכונים")]


def _csv_cell(v):
    if v is None: return ""
    if isinstance(v, bool): return "כן" if v else "לא"
    s = "; ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s          # CSV/formula injection guard


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO(); w = csv.writer(buf); w.writerow([h for _, h in _CSV_COLS])
    for r in rows:
        ex = r.get("extracted") or {}; flat = {**ex, "score": r.get("score"), "status": r.get("status"), "stage": r.get("stage"), "created": str(r.get("created") or "")[:16], "source_url": r.get("source_url"), "risks": r.get("risks")}
        w.writerow([_csv_cell(flat.get(k)) for k, _ in _CSV_COLS])
    return "\ufeff" + buf.getvalue()                                                # BOM so Excel opens Hebrew correctly


_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE00-\uFE0F\u200d\u200e\u200f\u202a-\u202e]")
_WA = re.compile(r"(?m)^\s*\[?\d{1,2}[./]\d{1,2}[./]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp][Mm])?\]?\s*[-–]?\s*[^:\n]{1,40}:\s*")
_NOISE = re.compile(r"(?mi)^.*(?:הצטרפו\s+ל|שתפו\s+|לחצו\s+כאן\s+להצטרפות|הודעה\s+זו\s+נמחקה|<מדיה\s+הושמטה>|<media\s+omitted>|this\s+message\s+was\s+deleted|forwarded).*$\n?")


def clean_paste(text: str, max_parts: int = 60) -> dict:
    """Cleans pasted WhatsApp/Facebook text and splits it into separate listings. Never changes prices or digits."""
    raw = (text or "")[:120000]; marks = list(_WA.finditer(raw))
    if len(marks) >= 2: parts = [raw[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(raw)] for i, m in enumerate(marks)]
    else: parts = re.split(r"\n\s*(?:-{3,}|={3,}|_{3,}|\*{3,})\s*\n|\n\s*\n\s*\n+", "\n" + raw.strip() + "\n")
    out = []
    for p in parts:
        p = _NOISE.sub("", p); p = _EMOJI.sub(" ", p)
        p = re.sub(r"(?<!\d)(?:\+?972|\(?00972\)?)[-\s]?(\d{1,2})[-\s]?(\d{3})[-\s]?(\d{4})(?!\d)", lambda m: f"0{m.group(1)}-{m.group(2)}-{m.group(3)}", p)
        p = re.sub(r"[ \t]+", " ", p); p = re.sub(r"\n{3,}", "\n\n", p).strip()
        if len(p) >= 15: out.append(p[:5000])
    return {"parts": out[:max_parts], "found": len(out), "source": "whatsapp" if len(marks) >= 2 else "plain", "dropped": max(0, len(out) - max_parts)}
