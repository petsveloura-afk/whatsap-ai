"""Outreach drafts (v3.10): a polite, human-sounding first message to the owner of a listing. Free and deterministic (no AI needed);
an optional AI polish uses the free brains when configured. The system NEVER sends anything to the owner by itself: the draft opens in
the user's own WhatsApp / mail app, and the message leaves only when the user presses send there."""
import hashlib, re

TONES = ("friendly", "formal", "short")
def _price(x: dict) -> str:
    p = x.get("price")
    if not p: return ""
    cur = {"ILS": "₪", "USD": "$", "EUR": "€"}.get(x.get("currency") or "ILS", "₪")
    return f"{p:,.0f} {cur}" if cur == "₪" else f"{cur}{p:,.0f}"
def _loc(x: dict) -> str:
    from .feeds import hebrew_name
    return hebrew_name(x.get("location")) or ""
def _in(city: str) -> str:
    """'חולון' -> 'בחולון'. Cities that already start with ב/ה keep the plain prefix, which reads fine in Hebrew."""
    return ("ב" + city) if city else ""
def _item(x: dict, category: str | None) -> tuple[str, str]:
    """-> (bare noun phrase without article, what to ask). Bare form lets us safely add ב / ל / על in front."""
    cat = category or x.get("category")
    loc = _in(_loc(x)); rooms = x.get("rooms")
    if cat == "real_estate":
        r = f" {rooms:g} חדרים" if rooms else ""
        return ((f"דירת{r}" if rooms else "דירה") + (" " + loc if loc else ""), "עדיין פנויה")
    if cat == "vehicles": return ("הרכב", "עדיין למכירה")
    if cat == "electronics": return ("המוצר", "עדיין זמין")
    return ("הפריט", "עדיין רלוונטי")
def _pre(prefix: str, thing: str) -> str:
    """prefix + noun, dropping the definite article: ב + הרכב -> ברכב."""
    return prefix + (thing[1:] if thing.startswith("ה") else thing)

def _feat(x: dict) -> str:
    names = {"parking": "חניה", "elevator": "מעלית", "balcony": "מרפסת", "safe_room": "ממ״ד", "storage": "מחסן", "ac": "מיזוג", "garden": "גינה"}
    f = [names[k] for k in (x.get("features") or []) if k in names][:2]
    return " וה".join(f)

def draft(extracted: dict | None, category: str | None = None, tone: str = "friendly", name: str | None = None, variant: int = 0) -> str:
    x = extracted or {}; tone = tone if tone in TONES else "friendly"
    thing, ask = _item(x, category); price = _price(x); sign = (name or "").strip()[:40]
    pr = f" ({price})" if price else ""; feat = _feat(x); tail = f"\n{sign}" if sign else ""
    if tone == "short":
        opts = [f"שלום, ראיתי את המודעה על {thing}{pr}. האם {ask}?", f"היי, מתעניין/ת {_pre('ב', thing)}. האם {ask}?"]
        return opts[variant % len(opts)] + tail
    if tone == "formal":
        opts = [
            f"שלום רב,\nראיתי את המודעה שלך על {thing}{(' במחיר ' + price) if price else ''} ואני מעוניין/ת לברר פרטים.\nהאם {ask}? אשמח לתאם שיחה קצרה או צפייה בזמן הנוח לך.\nתודה מראש,",
            f"שלום,\nפנייתי בנוגע {_pre('ל', thing)}{pr}. האם {ask}?\nאם כן, אודה לך אם תוכל/י לשלוח פרטים נוספים ולהציע מועד לפגישה.\nבתודה,",
        ]
        return opts[variant % len(opts)] + tail
    opts = [
        f"היי 🙂 ראיתי את המודעה על {thing}{pr} ונשמע לי מעניין{(', במיוחד ה' + feat) if feat else ''}.\nהאם {ask}? אשמח לשמוע עוד פרטים ולתאם לראות מתי שנוח לך.\nתודה רבה!",
        f"שלום, מה שלומך? ראיתי את המודעה על {thing}{pr}.\nהאם {ask}? אשמח אם נוכל לדבר ולקבוע זמן להיפגש.\nתודה!",
        f"היי, אני מתעניין/ת {_pre('ב', thing)}{(' שפירסמת ב-' + price) if price else ' שפירסמת'}.\nהאם {ask}? יהיה נהדר לקבל כמה פרטים ולתאם צפייה.\nמודה לך מראש 🙏",
    ]
    return opts[variant % len(opts)] + tail

def polish_prompt(text: str, tone: str) -> list[dict]:
    style = {"friendly": "חם, טבעי ואנושי", "formal": "מנומס ורשמי", "short": "קצר מאוד, שורה או שתיים"}.get(tone, "טבעי")
    return [{"role": "system", "content": "את/ה עוזר/ת שמשפר/ת הודעות פנייה קצרות בעברית למוכר של מודעה. שמור/י על כל העובדות כפי שהן, אל תוסיף/י מחירים, מספרי טלפון או הבטחות שלא בטקסט, ואל תכתוב/י הסברים. החזר/י רק את ההודעה המשופרת."},
            {"role": "user", "content": f"סגנון: {style}\nההודעה:\n{text}"}]

def safe_polished(orig: str, new: str) -> str | None:
    """Accepts the AI version only if it adds no digits (prices/phones) that were not in the draft and stays short."""
    new = (new or "").strip().strip('"')
    if not new or len(new) > 600: return None
    if set(re.findall(r"\d+", new)) - set(re.findall(r"\d+", orig)): return None
    return new
