"""Rule-based extraction (Hebrew/English), free and local. Backward compatible: the original keys
(category, rooms, location, price, currency, broker, condition, confidence) are kept; new keys are additive.
Unknown fields stay None. Nothing here calls an external service."""
import re

# ---- cities: alias -> canonical English name (aliases are normalised: no quotes/hyphens, 'קריית'->'קרית') ----
_CITY_SRC = {
    "Tel Aviv": ["תל אביב", "תל אביב יפו", "tel aviv", "tlv"], "Holon": ["חולון", "holon"], "Bat Yam": ["בת ים", "bat yam"],
    "Ramat Gan": ["רמת גן", "ramat gan"], "Givatayim": ["גבעתיים", "givatayim"], "Bnei Brak": ["בני ברק", "bnei brak"],
    "Petah Tikva": ["פתח תקווה", "פתח תקוה", "petah tikva", "petach tikva"], "Rishon LeZion": ["ראשון לציון", "ראשל צ", "rishon lezion", "rishon le zion"],
    "Rehovot": ["רחובות", "rehovot"], "Ashdod": ["אשדוד", "ashdod"], "Ashkelon": ["אשקלון", "ashkelon"],
    "Netanya": ["נתניה", "netanya"], "Herzliya": ["הרצליה", "herzliya"], "Raanana": ["רעננה", "raanana"], "Kfar Saba": ["כפר סבא", "kfar saba"],
    "Hod Hasharon": ["הוד השרון", "hod hasharon"], "Ramat Hasharon": ["רמת השרון", "ramat hasharon"], "Kiryat Ono": ["קרית אונו", "kiryat ono"],
    "Or Yehuda": ["אור יהודה", "or yehuda"], "Yehud": ["יהוד", "yehud"], "Lod": ["לוד", "lod"], "Ramla": ["רמלה", "ramla"],
    "Modiin": ["מודיעין", "modiin", "modi in"], "Nes Ziona": ["נס ציונה", "nes ziona"], "Yavne": ["יבנה", "yavne"], "Gedera": ["גדרה", "gedera"],
    "Jerusalem": ["ירושלים", "jerusalem"], "Beit Shemesh": ["בית שמש", "beit shemesh"], "Haifa": ["חיפה", "haifa"],
    "Kiryat Ata": ["קרית אתא", "kiryat ata"], "Kiryat Bialik": ["קרית ביאליק", "kiryat bialik"], "Kiryat Motzkin": ["קרית מוצקין", "kiryat motzkin"],
    "Kiryat Yam": ["קרית ים", "kiryat yam"], "Nesher": ["נשר", "nesher"], "Tirat Carmel": ["טירת כרמל", "tirat carmel"],
    "Akko": ["עכו", "akko", "acre"], "Nahariya": ["נהריה", "nahariya"], "Karmiel": ["כרמיאל", "karmiel"], "Afula": ["עפולה", "afula"],
    "Nazareth": ["נצרת", "nazareth"], "Tiberias": ["טבריה", "tiberias"], "Safed": ["צפת", "safed", "tzfat"], "Hadera": ["חדרה", "hadera"],
    "Zichron Yaakov": ["זכרון יעקב", "זיכרון יעקב", "zichron yaakov"], "Caesarea": ["קיסריה", "caesarea"], "Beer Sheva": ["באר שבע", "beer sheva", "beersheba"],
    "Eilat": ["אילת", "eilat"], "Dimona": ["דימונה", "dimona"], "Arad": ["ערד", "arad"], "Kiryat Gat": ["קרית גת", "kiryat gat"],
    "Kiryat Malachi": ["קרית מלאכי", "kiryat malachi"], "Sderot": ["שדרות", "sderot"], "Netivot": ["נתיבות", "netivot"], "Ofakim": ["אופקים", "ofakim"],
    "Rosh HaAyin": ["ראש העין", "rosh haayin", "rosh ha ayin"], "Elad": ["אלעד", "elad"], "Modiin Illit": ["מודיעין עילית", "modiin illit"],
    "Ariel": ["אריאל", "ariel"], "Maale Adumim": ["מעלה אדומים", "maale adumim"], "Tel Mond": ["תל מונד", "tel mond"], "Kfar Yona": ["כפר יונה", "kfar yona"],
    "Pardes Hanna": ["פרדס חנה", "pardes hanna"], "Binyamina": ["בנימינה", "binyamina"], "Yokneam": ["יקנעם", "yokneam"], "Migdal HaEmek": ["מגדל העמק", "migdal haemek"],
    "Kiryat Shmona": ["קרית שמונה", "kiryat shmona"], "Beit Shean": ["בית שאן", "beit shean"], "Umm al-Fahm": ["אום אל פחם", "umm al fahm"],
}
def _norm(t: str) -> str:
    t = t.lower().replace("קריית", "קרית").replace("״", '"').replace("”", '"').replace("“", '"').replace("׳", "'").replace("’", "'")
    t = re.sub(r"[\-–—_/]+", " ", t)
    return re.sub(r"\s+", " ", t)
CITIES = {}
for _canon, _aliases in _CITY_SRC.items():
    for _a in _aliases: CITIES[_norm(_a)] = _canon
_HEB_PRE = "ובלמהכש"
def _city_re(alias: str):
    if re.search(r"[א-ת]", alias):
        return re.compile(r"(?<![א-ת])[" + _HEB_PRE + r"]{0,2}" + re.escape(alias) + r"(?![א-ת])")
    return re.compile(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])")
_CITY_RE = [(_city_re(a), c) for a, c in sorted(CITIES.items(), key=lambda x: -len(x[0]))]

def find_cities(text: str) -> list[str]:
    """Canonical cities in order of first appearance (longest alias wins on overlap)."""
    t = _norm(text); hits = []; used = []
    for rx, c in _CITY_RE:
        for m in rx.finditer(t):
            if any(m.start() < e and m.end() > s for s, e in used): continue
            used.append((m.start(), m.end())); hits.append((m.start(), c))
    out = []
    for _, c in sorted(hits):
        if c not in out: out.append(c)
    return out

def canon_city(name: str | None) -> str | None:
    """Accepts Hebrew or English user input ('חולון', 'holon', 'Holon') -> canonical name, else the input unchanged."""
    if not name: return name
    n = _norm(name).strip()
    return CITIES.get(n) or next((c for c in _CITY_SRC if c.lower() == n), name)

# ---- numbers / money ----
def parse_number(s: str) -> float:
    s = s.strip().rstrip(".,")
    if "," in s: return float(s.replace(",", ""))
    if "." in s and re.fullmatch(r"\d{1,3}(\.\d{3})+", s): return float(s.replace(".", ""))
    return float(s)
_MULT = {"אלף": 1e3, "אלפים": 1e3, "k": 1e3, "מיליון": 1e6, "מליון": 1e6, "m": 1e6, "mln": 1e6, "million": 1e6}
_CUR = {"₪": "ILS", "ש\"ח": "ILS", "שח": "ILS", "שקל": "ILS", "שקלים": "ILS", "ils": "ILS", "nis": "ILS", "$": "USD", "usd": "USD", "דולר": "USD", "€": "EUR", "eur": "EUR", "אירו": "EUR"}
_CURW = r"(?:₪|ש\"ח|שח|שקלים|שקל|ils|nis|\$|usd|דולר|€|eur|אירו)"
_MULTW = r"(?:אלפים|אלף|מיליון|מליון|million|mln|k|m)"
_AFTER = re.compile(r"(\d[\d,\.]*\d|\d)\s*(" + _MULTW + r"\b)?\s*(" + _CURW + r")(?![א-תa-z])")
_BEFORE = re.compile(r"(" + _CURW + r")\s*(\d[\d,\.]*\d|\d)\s*(" + _MULTW + r"\b)?")
_LABELLED = re.compile(r"(?:מחיר|price|asking|שכירות|שכ\"ד|שכד|rent)\s*[:\-]?\s*(\d[\d,\.]*\d|\d)\s*(" + _MULTW + r"\b)?")
_FEE = re.compile(r"(ארנונה|ועד|וועד|דמי|עמלה|מקדמה|ביטוח)\s*\S{0,10}\s*$")
def find_price(t: str):
    """-> (price, currency) of the most plausible asking price, else (None, None)."""
    cands = []
    for m in _AFTER.finditer(t): cands.append((m.start(), m.group(1), m.group(2), m.group(3), m.start()))
    for m in _BEFORE.finditer(t): cands.append((m.start(), m.group(2), m.group(3), m.group(1), m.start()))
    for pos, num, mult, cur, st in sorted(cands):
        if _FEE.search(t[max(0, st - 18):st]): continue
        try: v = parse_number(num)
        except ValueError: continue
        v *= _MULT.get((mult or "").lower(), 1)
        if v <= 0: continue
        return v, _CUR.get(cur.lower(), "ILS")
    m = _LABELLED.search(t)
    if m:
        try: return parse_number(m.group(1)) * _MULT.get((m.group(2) or "").lower(), 1), "ILS"
        except ValueError: pass
    return None, None

# ---- vocab ----
_WORD_NUM = {"אחד": 1, "אחת": 1, "שתיים": 2, "שני": 2, "שתי": 2, "שלושה": 3, "שלוש": 3, "ארבעה": 4, "ארבע": 4, "חמישה": 5, "חמש": 5, "שישה": 6, "שש": 6}
_ROOMS_NUM = re.compile(r"(\d(?:\.5)?)(?:\s*[-–]\s*\d(?:\.5)?)?\s*(?:חדרים|חדר|חד['׳]?(?![א-ת])|rooms?\b|bedrooms?\b|br\b|-?room)")
_ROOMS_WORD = re.compile(r"(" + "|".join(_WORD_NUM) + r")(\s+וחצי)?\s+חדרים")
_SQM = re.compile(r"(\d{2,4})\s*(?:מ\"ר|מר\b|מטר רבוע|מטרים|sqm|sq\.?\s?m|m2|מ'ר)")
_FLOOR = re.compile(r"קומה\s*(\d{1,2})(?:\s*(?:מתוך|/)\s*(\d{1,2}))?|(\d{1,2})\s*(?:מתוך)\s*(\d{1,2})\s*קומות|קומת\s*(קרקע)")
_FEATURES = {"parking": ("חניה", "חנייה", "parking"), "elevator": ("מעלית", "elevator", "lift"), "balcony": ("מרפסת", "balcony"),
             "safe_room": ("ממ\"ד", "ממד", "safe room", "mamad"), "storage": ("מחסן", "storage room"), "ac": ("מזגן", "מיזוג", "air condition"),
             "furnished": ("מרוהט", "מרוהטת", "furnished"), "garden": ("גינה", "garden"), "accessible": ("נגיש", "accessible"), "pets": ("חיות מחמד", "pets allowed")}
_CAT_TERMS = {
    "real_estate": (("דירה", "דירת", "דירות", "פנטהאוז", "דופלקס", "סטודיו", "בית פרטי", "וילה", "מגרש", "קוטג", "חדרים", "מ\"ר", "apartment", "penthouse", "duplex", "studio", "villa", "flat", "bedroom", "sqm"), ("להשכרה", "שכירות", "למכירה נדלן", "for rent")),
    "vehicles": (("רכב", "מכונית", "אוטו", "אופנוע", "קטנוע", "טרקטורון", "ק\"מ", "קמ", "יד ראשונה", "יד שנייה", "car", "motorcycle", "suv", "hybrid", "הייבריד", "בנזין", "דיזל"), ("טסט", "רישיון רכב", "km")),
    "electronics": (("אייפון", "iphone", "סמסונג", "samsung", "גלקסי", "מחשב", "לפטופ", "laptop", "macbook", "מקבוק", "טלוויזיה", "טלויזיה", "tv", "אייפד", "ipad", "פלייסטיישן", "playstation", "xbox", "אוזניות", "airpods", "מסך", "מצלמה", "gb"), ("אחריות יבואן", "warranty", "ג'יגה", "גיגה")),
    "furniture": (("ספה", "שולחן", "כיסא", "כורסא", "מיטה", "ארון", "שידה", "sofa", "table", "chair", "bed", "wardrobe", "מקרר", "מכונת כביסה", "תנור"), ()),
}
_CARS = {"Toyota": ("טויוטה", "toyota"), "Hyundai": ("יונדאי", "hyundai"), "Kia": ("קיה", "kia"), "Mazda": ("מאזדה", "mazda"), "Skoda": ("סקודה", "skoda"),
         "Honda": ("הונדה", "honda"), "Suzuki": ("סוזוקי", "suzuki"), "Mitsubishi": ("מיצובישי", "mitsubishi"), "Nissan": ("ניסאן", "nissan"),
         "Volkswagen": ("פולקסווגן", "volkswagen", "vw"), "Audi": ("אאודי", "audi"), "BMW": ("במוו", "bmw", "ב.מ.וו"), "Mercedes": ("מרצדס", "mercedes"),
         "Tesla": ("טסלה", "tesla"), "Chevrolet": ("שברולט", "chevrolet"), "Ford": ("פורד", "ford"), "Seat": ("סיאט", "seat"), "Opel": ("אופל", "opel"),
         "Peugeot": ("פיג'ו", "פיגו", "peugeot"), "Citroen": ("סיטרואן", "citroen"), "Renault": ("רנו", "renault"), "Volvo": ("וולוו", "volvo"),
         "Subaru": ("סובארו", "subaru"), "Lexus": ("לקסוס", "lexus"), "Mini": ("מיני קופר", "mini cooper"), "Fiat": ("פיאט", "fiat"), "BYD": ("בי וואי די", "byd"), "MG": ("אם ג'י", "mg motor")}
_DEVICES = {"Apple": ("אייפון", "iphone", "אייפד", "ipad", "מקבוק", "macbook", "airpods", "אפל"), "Samsung": ("סמסונג", "samsung", "גלקסי", "galaxy"), "Xiaomi": ("שיאומי", "xiaomi", "redmi"),
            "Google": ("פיקסל", "pixel"), "Lenovo": ("לנובו", "lenovo"), "Dell": ("דל ", "dell"), "HP": ("hp ", "אייצ' פי"), "Asus": ("אסוס", "asus"), "Sony": ("סוני", "sony", "playstation", "פלייסטיישן"), "LG": ("lg ", "אל ג'י"), "Microsoft": ("xbox", "אקסבוקס", "surface")}
_NEG_RENO = re.compile(r"לא\s*משופץ|לא\s*משופצת|ללא\s*שיפוץ|דורש(?:ת)?\s*שיפוץ|needs?\s*renovation|to renovate|במצב\s*גרוע|דורשת\s*שדרוג")
_SCAM = [("Asks for advance payment before viewing", r"מקדמה\s*לפני|תעביר(?:ו)?\s*(?:כסף|מקדמה)|העברה\s*לפני|ביט\s*לפני|western union|advance payment|deposit before|wire (?:the )?money|שלח(?:ו)? כסף"),
         ("Owner 'abroad' and keys by mail", r"בחו\"ל[^.]{0,40}(?:מפתח|דואר|שליח)|keys? (?:by|via) (?:mail|courier)|owner (?:is )?abroad"),
         ("Contact only through chat apps", r"רק\s*(?:ב)?(?:וואטסאפ|ווטסאפ|טלגרם)|whatsapp only|telegram only|no calls"),
         ("Pressure/urgency language", r"רק\s*היום|מי שראשון|פעם בחיים|last chance|act now|only today|limited offer"),
         ("Requests gift cards / crypto", r"גיפט\s*קארד|gift ?card|crypto|ביטקוין|bitcoin|usdt")]
_SCAM = [(m, re.compile(p, re.I)) for m, p in _SCAM]

_WRE = {}
def _wre(w):
    w = w.strip()
    if w not in _WRE:
        if re.search(r"[א-ת]", w[:1]): head = r"(?<![א-ת])[" + _HEB_PRE + r"]{0,2}"
        else: head = r"(?<![a-z0-9])"
        tail = r"(?![א-ת])" if re.search(r"[א-ת]", w[-1:]) else (r"(?![a-z])" if re.search(r"[a-z]", w[-1:]) else "")
        _WRE[w] = re.compile(head + re.escape(w) + tail)
    return _WRE[w]
def _has(t, words): return any(_wre(w).search(t) for w in words)
def _detect_category(t: str):
    best, bs = None, 0
    for cat, (strong, weak) in _CAT_TERMS.items():
        s = sum(2 for w in strong if _wre(w).search(t)) + sum(1 for w in weak if _wre(w).search(t))
        if cat == "vehicles" and any(_has(t, v) for v in _CARS.values()): s += 3
        if cat == "electronics" and any(_has(t, v) for v in _DEVICES.values()): s += 2
        if s > bs: best, bs = cat, s
    return best if bs >= 2 else None
def detect_category(text: str): return _detect_category(_norm(text))

def extract(text: str) -> dict:
    t = _norm(text)
    out = {"category": None, "rooms": None, "location": None, "price": None, "currency": None, "broker": None, "condition": None}
    out["price"], out["currency"] = find_price(t)
    m = _ROOMS_NUM.search(t)
    if m: out["rooms"] = float(m.group(1))
    else:
        m = _ROOMS_WORD.search(t)
        if m: out["rooms"] = _WORD_NUM[m.group(1)] + (0.5 if m.group(2) else 0)
        elif "סטודיו" in t or "studio" in t: out["rooms"] = 1.0
    cities = find_cities(text)
    if cities: out["location"] = cities[0]
    if len(cities) > 1: out["other_locations"] = cities[1:]
    out["category"] = _detect_category(t)
    if re.search(r"(?:ללא|בלי|אין|לא)\s*(?:דמי\s*)?(?:תיווך|מתווך)|no broker|without (?:a )?broker|no agent|מבעלים|ישירות מהבעלים|מוכר פרטי|by owner|direct from owner", t): out["broker"] = False
    elif re.search(r"תיווך|מתווך|סוכנות|broker|agency|agent\b|רימקס|re/max|אנגלו סכסון|century 21", t): out["broker"] = True
    if _NEG_RENO.search(t): out["condition"] = "needs_renovation"
    elif re.search(r"משופץ|משופצת|שופצה|renovated|refurbished", t): out["condition"] = "renovated"
    elif re.search(r"חדש(?:ה)? מקבלן|חדשה לגמרי|brand new|new build|חדש באריזה|sealed", t): out["condition"] = "new"
    elif re.search(r"במצב\s*(?:מצוין|טוב|מעולה)|מצב\s*(?:מצוין|טוב)|like new|excellent condition|good condition|שמורה", t): out["condition"] = "good"
    # additive fields
    out["deal_type"] = "rent" if re.search(r"להשכרה|לחודש|שכירות|שכ\"ד|for rent|per month|/mo\b", t) else "sale" if re.search(r"למכירה|for sale|מכירה", t) else None
    m = _SQM.search(t); out["area_sqm"] = float(m.group(1)) if m else None
    out["floor"] = out["total_floors"] = None
    m = _FLOOR.search(t)
    if m:
        if m.group(5): out["floor"] = 0
        elif m.group(1): out["floor"] = int(m.group(1)); out["total_floors"] = int(m.group(2)) if m.group(2) else None
        elif m.group(3): out["floor"] = int(m.group(3)); out["total_floors"] = int(m.group(4))
    out["features"] = [k for k, ws in _FEATURES.items() if _has(t, ws)]
    out["brand"] = out["model"] = out["year"] = out["km"] = out["hand"] = out["storage_gb"] = None
    cat = out["category"]
    if cat == "vehicles" or cat is None:
        for b, ws in _CARS.items():
            if _has(t, ws): out["brand"] = b; break
        m = re.search(r"(?:שנת|שנה|year|דגם|model)\s*[:\-]?\s*((?:19|20)\d\d)\b|\b((?:19[89]\d|20[0-3]\d))\s*(?:מודל|model)", t)
        if m: out["year"] = int(m.group(1) or m.group(2))
        m = re.search(r"(\d[\d,\.]*)\s*(אלף\s*)?(?:ק\"מ|קמ|km|קילומטר)", t)
        if m:
            try: out["km"] = int(parse_number(m.group(1)) * (1000 if m.group(2) or parse_number(m.group(1)) < 1000 and re.search(r"אלף", t[m.start():m.end() + 6]) else 1))
            except ValueError: pass
        m = re.search(r"יד\s*(ראשונה|שנייה|שניה|שלישית|רביעית|\d)|(\d)(?:st|nd|rd|th)\s*hand", t)
        if m:
            g = m.group(1) or m.group(2); out["hand"] = {"ראשונה": 1, "שנייה": 2, "שניה": 2, "שלישית": 3, "רביעית": 4}.get(g) or (int(g) if str(g).isdigit() else None)
        if out["category"] is None and (out["brand"] and (out["km"] or out["year"])): out["category"] = "vehicles"
    if cat == "electronics" or cat is None:
        for b, ws in _DEVICES.items():
            if _has(t, ws): out["brand"] = out["brand"] or b; break
        m = re.search(r"iphone\s*(\d{1,2})\s*(pro max|pro|plus|mini)?|אייפון\s*(\d{1,2})\s*(פרו מקס|פרו|פלוס|מיני)?", t)
        if m: out["model"] = ("iPhone " + (m.group(1) or m.group(3)) + (" " + (m.group(2) or {"פרו מקס": "pro max", "פרו": "pro", "פלוס": "plus", "מיני": "mini"}.get(m.group(4), "")) if (m.group(2) or m.group(4)) else "")).strip()
        m = re.search(r"(\d{2,4})\s*(?:gb|גיגה|ג'יגה|גיגה בייט)\b|(\d)\s*(?:tb|טרה)", t)
        if m: out["storage_gb"] = int(m.group(1)) if m.group(1) else int(m.group(2)) * 1024
        if out["category"] is None and (out["model"] or (out["brand"] and out["storage_gb"])): out["category"] = "electronics"
    out["negotiable"] = True if re.search(r"גמיש|ניתן להתמקח|לא סופי|negotiable|or best offer|\bobo\b|פתוח להצעות", t) else None
    out["urgent"] = True if re.search(r"דחוף|מכירה דחופה|urgent|בהזדמנות|הזדמנות|quick sale", t) else None
    if out["price"] and out["area_sqm"] and out["category"] == "real_estate": out["price_per_sqm"] = round(out["price"] / out["area_sqm"])
    flags = [msg for msg, rx in _SCAM if rx.search(t)]
    if text.count("!") >= 5: flags.append("Excessive exclamation marks")
    if flags: out["flags"] = flags
    cat = out["category"]
    core = {"real_estate": ("price", "location", "rooms"), "vehicles": ("price", "brand", "year", "km"), "electronics": ("price", "brand", "model"), "furniture": ("price",)}.get(cat, ("price", "location"))
    base = sum(out.get(k) is not None for k in core) + (1 if cat else 0)
    extras = sum(bool(out.get(k)) is True or (out.get(k) not in (None, [], False)) for k in ("condition", "broker", "area_sqm", "floor", "deal_type", "features"))
    out["confidence"] = round(0.8 * base / (len(core) + 1) + 0.2 * min(extras, 3) / 3, 2)
    return out
