// GENERATED from backend/app/categories.py (python scripts/gen_catalog.py). Offline fallback for the pickers: the UI works even if /api/categories is unreachable.
export type CatalogItem = { key: string; label: string; group: string; icon: string; subs: [string, string][] };
export const CATALOG: CatalogItem[] = [
 {
  "key": "real_estate",
  "label": "נדל״ן",
  "group": "נדל״ן",
  "icon": "🏠",
  "subs": [
   [
    "apartment_sale",
    "דירה למכירה"
   ],
   [
    "apartment_rent",
    "דירה להשכרה"
   ],
   [
    "penthouse",
    "פנטהאוז / דופלקס"
   ],
   [
    "garden_apt",
    "דירת גן"
   ],
   [
    "private_house",
    "בית פרטי / וילה"
   ],
   [
    "studio",
    "סטודיו / יחידת דיור"
   ],
   [
    "new_project",
    "פרויקט חדש מקבלן"
   ],
   [
    "sublet",
    "סאבלט"
   ]
  ]
 },
 {
  "key": "vehicles",
  "label": "רכב",
  "group": "רכב ותחבורה",
  "icon": "🚗",
  "subs": [
   [
    "private_car",
    "רכב פרטי"
   ],
   [
    "suv",
    "ג׳יפ / SUV"
   ],
   [
    "luxury",
    "יוקרה"
   ],
   [
    "ev_hybrid",
    "חשמלי / הייבריד"
   ],
   [
    "minivan",
    "מיניוואן / 7 מקומות"
   ],
   [
    "lease_takeover",
    "העברת ליסינג"
   ],
   [
    "classic",
    "אספנות / קלאסי"
   ]
  ]
 },
 {
  "key": "electronics",
  "label": "אלקטרוניקה",
  "group": "אלקטרוניקה",
  "icon": "📱",
  "subs": [
   [
    "phones",
    "טלפונים"
   ],
   [
    "laptops",
    "מחשבים ניידים"
   ],
   [
    "tablets",
    "טאבלטים"
   ],
   [
    "tv",
    "טלוויזיות ומסכים"
   ],
   [
    "headphones",
    "אוזניות ורמקולים"
   ],
   [
    "wearables",
    "שעונים חכמים"
   ],
   [
    "accessories",
    "אביזרים"
   ]
  ]
 },
 {
  "key": "furniture",
  "label": "ריהוט",
  "group": "בית וגן",
  "icon": "🛋️",
  "subs": [
   [
    "sofas",
    "ספות וכורסאות"
   ],
   [
    "beds",
    "מיטות ומזרנים"
   ],
   [
    "tables",
    "שולחנות וכיסאות"
   ],
   [
    "wardrobes",
    "ארונות ושידות"
   ],
   [
    "kitchen",
    "מטבחים"
   ],
   [
    "lighting",
    "תאורה"
   ],
   [
    "office_furn",
    "ריהוט משרדי"
   ]
  ]
 },
 {
  "key": "business",
  "label": "עסקים",
  "group": "עסקים ותעסוקה",
  "icon": "💼",
  "subs": [
   [
    "franchise",
    "זכיינות"
   ],
   [
    "for_sale",
    "עסק למכירה"
   ],
   [
    "partner",
    "שותפים והשקעות"
   ],
   [
    "supplier",
    "ספקים וסיטונאות"
   ],
   [
    "equipment",
    "ציוד עסקי"
   ]
  ]
 },
 {
  "key": "services",
  "label": "שירותים",
  "group": "שירותים",
  "icon": "🛠️",
  "subs": [
   [
    "repairs",
    "תיקונים"
   ],
   [
    "cleaning",
    "ניקיון"
   ],
   [
    "design",
    "עיצוב ובנייה"
   ],
   [
    "legal",
    "משפט וחשבונאות"
   ],
   [
    "tech_srv",
    "שירותי טכנולוגיה"
   ]
  ]
 },
 {
  "key": "other",
  "label": "אחר",
  "group": "אחר",
  "icon": "📦",
  "subs": [
   [
    "misc",
    "שונות"
   ],
   [
    "free",
    "למסירה / חינם"
   ],
   [
    "lost_found",
    "אבדות ומציאות"
   ]
  ]
 },
 {
  "key": "commercial_re",
  "label": "נדל״ן מסחרי",
  "group": "נדל״ן",
  "icon": "🏢",
  "subs": [
   [
    "office",
    "משרדים"
   ],
   [
    "shop",
    "חנויות"
   ],
   [
    "warehouse",
    "מחסנים ולוגיסטיקה"
   ],
   [
    "clinic",
    "קליניקות"
   ],
   [
    "coworking",
    "חללי עבודה משותפים"
   ]
  ]
 },
 {
  "key": "land",
  "label": "קרקעות ומגרשים",
  "group": "נדל״ן",
  "icon": "🌍",
  "subs": [
   [
    "building_plot",
    "מגרש לבנייה"
   ],
   [
    "agri",
    "קרקע חקלאית"
   ],
   [
    "investment",
    "קרקע להשקעה"
   ]
  ]
 },
 {
  "key": "vacation_rentals",
  "label": "צימרים ונופש",
  "group": "נדל״ן",
  "icon": "🏡",
  "subs": [
   [
    "cabin",
    "בקתות וצימרים"
   ],
   [
    "villa",
    "וילות נופש"
   ],
   [
    "apartment",
    "דירות נופש"
   ],
   [
    "glamping",
    "גלמפינג"
   ]
  ]
 },
 {
  "key": "roommates",
  "label": "שותפים לדירה",
  "group": "נדל״ן",
  "icon": "🛏️",
  "subs": [
   [
    "room",
    "חדר בדירה"
   ],
   [
    "students",
    "דירות סטודנטים"
   ],
   [
    "sublet",
    "סאבלט"
   ]
  ]
 },
 {
  "key": "motorcycles",
  "label": "אופנועים וקטנועים",
  "group": "רכב ותחבורה",
  "icon": "🏍️",
  "subs": [
   [
    "road",
    "כביש"
   ],
   [
    "scooter",
    "קטנועים"
   ],
   [
    "offroad",
    "שטח וטרקטורונים"
   ],
   [
    "e_scooter",
    "קורקינט חשמלי"
   ]
  ]
 },
 {
  "key": "trucks",
  "label": "משאיות ורכב מסחרי",
  "group": "רכב ותחבורה",
  "icon": "🚚",
  "subs": [
   [
    "pickup",
    "טנדרים"
   ],
   [
    "van",
    "ואנים"
   ],
   [
    "heavy",
    "משאיות כבדות"
   ],
   [
    "bus",
    "אוטובוסים ומיניבוסים"
   ],
   [
    "forklift",
    "מלגזות ומנופים"
   ]
  ]
 },
 {
  "key": "boats",
  "label": "כלי שיט",
  "group": "רכב ותחבורה",
  "icon": "⛵",
  "subs": [
   [
    "motorboat",
    "סירות מנוע"
   ],
   [
    "sail",
    "מפרשיות"
   ],
   [
    "jetski",
    "אופנועי ים"
   ],
   [
    "kayak",
    "קיאקים וסאפ"
   ]
  ]
 },
 {
  "key": "car_parts",
  "label": "חלפים לרכב",
  "group": "רכב ותחבורה",
  "icon": "⚙️",
  "subs": [
   [
    "tires",
    "צמיגים וג׳אנטים"
   ],
   [
    "engine",
    "מנוע ותיבה"
   ],
   [
    "body",
    "פחחות ופנסים"
   ],
   [
    "audio",
    "מערכות שמע"
   ],
   [
    "accessories",
    "אביזרים"
   ]
  ]
 },
 {
  "key": "bicycles",
  "label": "אופניים ואופניים חשמליים",
  "group": "רכב ותחבורה",
  "icon": "🚲",
  "subs": [
   [
    "mtb",
    "אופני הרים"
   ],
   [
    "road",
    "אופני כביש"
   ],
   [
    "ebike",
    "אופניים חשמליים"
   ],
   [
    "kids",
    "אופני ילדים"
   ],
   [
    "city",
    "אופני עיר"
   ]
  ]
 },
 {
  "key": "smartphones",
  "label": "סלולר וטלפונים חכמים",
  "group": "אלקטרוניקה",
  "icon": "📲",
  "subs": [
   [
    "iphone",
    "אייפון"
   ],
   [
    "galaxy",
    "גלקסי"
   ],
   [
    "xiaomi",
    "שיאומי ואחרים"
   ],
   [
    "refurb",
    "מחודש"
   ],
   [
    "accessories",
    "אביזרי סלולר"
   ]
  ]
 },
 {
  "key": "computers",
  "label": "מחשבים וציוד היקפי",
  "group": "אלקטרוניקה",
  "icon": "💻",
  "subs": [
   [
    "desktop",
    "מחשבים נייחים"
   ],
   [
    "gpu",
    "כרטיסי מסך"
   ],
   [
    "monitors",
    "מסכים"
   ],
   [
    "printers",
    "מדפסות וסורקים"
   ],
   [
    "network",
    "ציוד רשת"
   ]
  ]
 },
 {
  "key": "gaming",
  "label": "גיימינג וקונסולות",
  "group": "אלקטרוניקה",
  "icon": "🎮",
  "subs": [
   [
    "ps",
    "פלייסטיישן"
   ],
   [
    "xbox",
    "אקסבוקס"
   ],
   [
    "switch",
    "נינטנדו"
   ],
   [
    "games",
    "משחקים"
   ],
   [
    "vr",
    "מציאות מדומה"
   ]
  ]
 },
 {
  "key": "cameras",
  "label": "צילום ודרונים",
  "group": "אלקטרוניקה",
  "icon": "📷",
  "subs": [
   [
    "dslr",
    "מצלמות רפלקס ומירורלס"
   ],
   [
    "lenses",
    "עדשות"
   ],
   [
    "action",
    "מצלמות אקשן"
   ],
   [
    "drones",
    "דרונים"
   ],
   [
    "studio",
    "ציוד סטודיו"
   ]
  ]
 },
 {
  "key": "audio",
  "label": "אודיו והיי-פיי",
  "group": "אלקטרוניקה",
  "icon": "🔊",
  "subs": [
   [
    "speakers",
    "רמקולים"
   ],
   [
    "amps",
    "מגברים ונגנים"
   ],
   [
    "home_cinema",
    "קולנוע ביתי"
   ],
   [
    "turntable",
    "פטיפונים"
   ],
   [
    "dj",
    "ציוד די-ג׳יי"
   ]
  ]
 },
 {
  "key": "smart_home",
  "label": "בית חכם ואבטחה",
  "group": "אלקטרוניקה",
  "icon": "🏠",
  "subs": [
   [
    "cameras",
    "מצלמות אבטחה"
   ],
   [
    "locks",
    "מנעולים חכמים"
   ],
   [
    "lighting",
    "תאורה חכמה"
   ],
   [
    "robot",
    "שואבים רובוטיים"
   ],
   [
    "alarm",
    "אזעקות"
   ]
  ]
 },
 {
  "key": "appliances",
  "label": "מוצרי חשמל לבית",
  "group": "בית וגן",
  "icon": "🧊",
  "subs": [
   [
    "fridge",
    "מקררים ומקפיאים"
   ],
   [
    "laundry",
    "כביסה וייבוש"
   ],
   [
    "kitchen",
    "מטבח"
   ],
   [
    "ac",
    "מיזוג אוויר"
   ],
   [
    "small",
    "מוצרי חשמל קטנים"
   ]
  ]
 },
 {
  "key": "garden",
  "label": "גינה, חוץ ופרגולות",
  "group": "בית וגן",
  "icon": "🌳",
  "subs": [
   [
    "pergola",
    "פרגולות וצל"
   ],
   [
    "garden_furn",
    "ריהוט גן"
   ],
   [
    "pool",
    "בריכות וג׳קוזי"
   ],
   [
    "bbq",
    "מנגלים"
   ],
   [
    "plants",
    "צמחים ועציצים"
   ]
  ]
 },
 {
  "key": "tools",
  "label": "כלי עבודה ומכשור",
  "group": "בית וגן",
  "icon": "🔧",
  "subs": [
   [
    "power",
    "כלי עבודה חשמליים"
   ],
   [
    "hand",
    "כלי עבודה ידניים"
   ],
   [
    "compressor",
    "מדחסים ומחוללים"
   ],
   [
    "welding",
    "ריתוך"
   ],
   [
    "measure",
    "מכשור ומדידה"
   ]
  ]
 },
 {
  "key": "building_materials",
  "label": "חומרי בניין ושיפוצים",
  "group": "בית וגן",
  "icon": "🧱",
  "subs": [
   [
    "tiles",
    "ריצוף וחיפוי"
   ],
   [
    "doors",
    "דלתות וחלונות"
   ],
   [
    "plumbing",
    "אינסטלציה וסניטריה"
   ],
   [
    "paint",
    "צבעים וטיח"
   ],
   [
    "stone",
    "אבן ושיש"
   ]
  ]
 },
 {
  "key": "fashion",
  "label": "אופנה והלבשה",
  "group": "אופנה וילדים",
  "icon": "👗",
  "subs": [
   [
    "women",
    "אופנת נשים"
   ],
   [
    "men",
    "אופנת גברים"
   ],
   [
    "shoes",
    "נעליים"
   ],
   [
    "bridal",
    "שמלות כלה וערב"
   ],
   [
    "bags",
    "תיקים ואביזרים"
   ]
  ]
 },
 {
  "key": "jewelry",
  "label": "תכשיטים ושעונים",
  "group": "אופנה וילדים",
  "icon": "💍",
  "subs": [
   [
    "rings",
    "טבעות"
   ],
   [
    "watches",
    "שעונים"
   ],
   [
    "necklaces",
    "שרשראות ותליונים"
   ],
   [
    "diamonds",
    "יהלומים ואבנים"
   ],
   [
    "bullion",
    "זהב וכסף להשקעה"
   ]
  ]
 },
 {
  "key": "baby_kids",
  "label": "תינוקות וילדים",
  "group": "אופנה וילדים",
  "icon": "👶",
  "subs": [
   [
    "strollers",
    "עגלות וטיולונים"
   ],
   [
    "car_seats",
    "כסאות בטיחות"
   ],
   [
    "furniture",
    "ריהוט לתינוק"
   ],
   [
    "clothes",
    "בגדי ילדים"
   ],
   [
    "feeding",
    "האכלה והנקה"
   ]
  ]
 },
 {
  "key": "toys",
  "label": "צעצועים ומשחקים",
  "group": "אופנה וילדים",
  "icon": "🧸",
  "subs": [
   [
    "lego",
    "לגו ובנייה"
   ],
   [
    "board",
    "משחקי קופסה"
   ],
   [
    "dolls",
    "בובות"
   ],
   [
    "cards",
    "קלפי אספנות"
   ],
   [
    "outdoor",
    "משחקי חוץ"
   ]
  ]
 },
 {
  "key": "sports",
  "label": "ציוד ספורט",
  "group": "פנאי וספורט",
  "icon": "⚽",
  "subs": [
   [
    "ball",
    "ספורט כדור"
   ],
   [
    "racket",
    "טניס וחבטות"
   ],
   [
    "water",
    "ספורט מים"
   ],
   [
    "winter",
    "סקי וסנובורד"
   ],
   [
    "martial",
    "אומנויות לחימה"
   ]
  ]
 },
 {
  "key": "fitness",
  "label": "ציוד כושר",
  "group": "פנאי וספורט",
  "icon": "🏋️",
  "subs": [
   [
    "cardio",
    "קרדיו"
   ],
   [
    "weights",
    "משקולות וכוח"
   ],
   [
    "home_gym",
    "ג׳ים ביתי"
   ],
   [
    "yoga",
    "יוגה ופילאטיס"
   ],
   [
    "recovery",
    "התאוששות"
   ]
  ]
 },
 {
  "key": "camping",
  "label": "קמפינג וטיולים",
  "group": "פנאי וספורט",
  "icon": "⛺",
  "subs": [
   [
    "tents",
    "אוהלים"
   ],
   [
    "sleeping",
    "שקי שינה וציוד לינה"
   ],
   [
    "backpacks",
    "תרמילים"
   ],
   [
    "cooking",
    "בישול בשטח"
   ],
   [
    "caravan",
    "קרוואנים ושטח"
   ]
  ]
 },
 {
  "key": "music_instruments",
  "label": "כלי נגינה",
  "group": "פנאי וספורט",
  "icon": "🎸",
  "subs": [
   [
    "guitar",
    "גיטרות ובס"
   ],
   [
    "keys",
    "פסנתרים וקלידים"
   ],
   [
    "drums",
    "תופים ושירה"
   ],
   [
    "strings",
    "כלי קשת"
   ],
   [
    "wind",
    "כלי נשיפה"
   ]
  ]
 },
 {
  "key": "books",
  "label": "ספרים ולימוד",
  "group": "פנאי וספורט",
  "icon": "📚",
  "subs": [
   [
    "textbooks",
    "ספרי לימוד"
   ],
   [
    "fiction",
    "ספרות"
   ],
   [
    "kids",
    "ספרי ילדים"
   ],
   [
    "holy",
    "ספרי קודש"
   ],
   [
    "comics",
    "קומיקס ומנגה"
   ]
  ]
 },
 {
  "key": "collectibles",
  "label": "אספנות ואמנות",
  "group": "פנאי וספורט",
  "icon": "🖼️",
  "subs": [
   [
    "coins",
    "מטבעות ושטרות"
   ],
   [
    "stamps",
    "בולים"
   ],
   [
    "art",
    "ציורים ופסלים"
   ],
   [
    "antiques",
    "אנטיקות"
   ],
   [
    "vinyl",
    "תקליטים"
   ]
  ]
 },
 {
  "key": "pets",
  "label": "חיות מחמד",
  "group": "אופנה וילדים",
  "icon": "🐶",
  "subs": [
   [
    "dogs",
    "כלבים"
   ],
   [
    "cats",
    "חתולים"
   ],
   [
    "birds",
    "ציפורים"
   ],
   [
    "fish",
    "דגים ואקווריום"
   ],
   [
    "supplies",
    "ציוד ומזון לחיות"
   ]
  ]
 },
 {
  "key": "tickets",
  "label": "כרטיסים והופעות",
  "group": "פנאי וספורט",
  "icon": "🎟️",
  "subs": [
   [
    "concerts",
    "הופעות"
   ],
   [
    "sports",
    "משחקי ספורט"
   ],
   [
    "theater",
    "תיאטרון והצגות"
   ],
   [
    "festivals",
    "פסטיבלים"
   ],
   [
    "kids",
    "אירועי ילדים"
   ]
  ]
 },
 {
  "key": "jobs",
  "label": "דרושים ותעסוקה",
  "group": "עסקים ותעסוקה",
  "icon": "👔",
  "subs": [
   [
    "fulltime",
    "משרה מלאה"
   ],
   [
    "parttime",
    "משרה חלקית"
   ],
   [
    "freelance",
    "פרילנס"
   ],
   [
    "hightech",
    "הייטק"
   ],
   [
    "students",
    "סטודנטים"
   ]
  ]
 },
 {
  "key": "courses",
  "label": "קורסים ושיעורים פרטיים",
  "group": "שירותים",
  "icon": "🎓",
  "subs": [
   [
    "tutoring",
    "שיעורים פרטיים"
   ],
   [
    "languages",
    "שפות"
   ],
   [
    "professional",
    "קורסים מקצועיים"
   ],
   [
    "music",
    "שיעורי נגינה"
   ],
   [
    "kids_clubs",
    "חוגים לילדים"
   ]
  ]
 },
 {
  "key": "event_services",
  "label": "אירועים והפקות",
  "group": "שירותים",
  "icon": "🎉",
  "subs": [
   [
    "venues",
    "אולמות וגנים"
   ],
   [
    "catering",
    "קייטרינג"
   ],
   [
    "photo",
    "צילום ווידאו"
   ],
   [
    "music",
    "להקות ו-DJ"
   ],
   [
    "rentals",
    "השכרת ציוד לאירועים"
   ]
  ]
 },
 {
  "key": "home_services",
  "label": "שירותי בית ושיפוצים",
  "group": "שירותים",
  "icon": "🧰",
  "subs": [
   [
    "plumber",
    "אינסטלציה"
   ],
   [
    "electric",
    "חשמל"
   ],
   [
    "painting",
    "צבעות"
   ],
   [
    "renovation",
    "שיפוץ כללי"
   ],
   [
    "pest",
    "הדברה וניקיון"
   ]
  ]
 },
 {
  "key": "moving",
  "label": "הובלות ואחסון",
  "group": "שירותים",
  "icon": "📦",
  "subs": [
   [
    "apartment",
    "הובלת דירה"
   ],
   [
    "pianos",
    "הובלת פסנתרים וכבדים"
   ],
   [
    "storage",
    "אחסנה"
   ],
   [
    "junk",
    "פינוי פסולת"
   ],
   [
    "international",
    "הובלות בינלאומיות"
   ]
  ]
 },
 {
  "key": "health_beauty",
  "label": "בריאות ויופי",
  "group": "שירותים",
  "icon": "💆",
  "subs": [
   [
    "cosmetics",
    "קוסמטיקה וטיפוח"
   ],
   [
    "massage",
    "עיסוי וספא"
   ],
   [
    "physio",
    "פיזיותרפיה וריפוי"
   ],
   [
    "hair",
    "שיער וציפורניים"
   ],
   [
    "nutrition",
    "תזונה וכושר אישי"
   ]
  ]
 },
 {
  "key": "medical_equipment",
  "label": "ציוד רפואי ושיקום",
  "group": "שירותים",
  "icon": "🩺",
  "subs": [
   [
    "mobility",
    "ניידות"
   ],
   [
    "beds",
    "מיטות ומזרנים סיעודיים"
   ],
   [
    "hearing",
    "שמיעה וראייה"
   ],
   [
    "home_care",
    "ציוד טיפול בית"
   ],
   [
    "dental",
    "ציוד רפואי מקצועי"
   ]
  ]
 },
 {
  "key": "industrial",
  "label": "ציוד תעשייתי וחקלאי",
  "group": "עסקים ותעסוקה",
  "icon": "🏭",
  "subs": [
   [
    "cnc",
    "מכונות CNC ועיבוד"
   ],
   [
    "packing",
    "אריזה וייצור"
   ],
   [
    "agri",
    "ציוד חקלאי"
   ],
   [
    "power",
    "גנרטורים ואנרגיה"
   ],
   [
    "lift",
    "הרמה ומשטחים"
   ]
  ]
 },
 {
  "key": "business_for_sale",
  "label": "עסקים למכירה וזכיינות",
  "group": "עסקים ותעסוקה",
  "icon": "🏪",
  "subs": [
   [
    "restaurant",
    "מסעדות וקפה"
   ],
   [
    "retail",
    "חנויות וקמעונאות"
   ],
   [
    "service",
    "עסקי שירות"
   ],
   [
    "online",
    "עסקים אונליין"
   ],
   [
    "franchise",
    "זכיינות"
   ]
  ]
 },
 {
  "key": "travel",
  "label": "טיסים וחבילות נופש",
  "group": "פנאי וספורט",
  "icon": "✈️",
  "subs": [
   [
    "flights",
    "טיסות"
   ],
   [
    "hotels",
    "מלונות"
   ],
   [
    "packages",
    "חבילות נופש"
   ],
   [
    "cruise",
    "קרוזים"
   ],
   [
    "transfer",
    "העברת הזמנות"
   ]
  ]
 },
 {
  "key": "food_equipment",
  "label": "ציוד למסעדות ובתי קפה",
  "group": "עסקים ותעסוקה",
  "icon": "🍽️",
  "subs": [
   [
    "coffee",
    "מכונות קפה"
   ],
   [
    "ovens",
    "תנורים וגריל"
   ],
   [
    "fridge",
    "קירור מסחרי"
   ],
   [
    "furniture",
    "ריהוט למסעדות"
   ],
   [
    "bakery",
    "קונדיטוריה ומאפייה"
   ]
  ]
 },
 {
  "key": "parking_storage",
  "label": "חניות ומחסנים",
  "group": "נדל״ן",
  "icon": "🅿️",
  "subs": [
   [
    "parking_rent",
    "חניה להשכרה"
   ],
   [
    "parking_sale",
    "חניה למכירה"
   ],
   [
    "covered",
    "חניה מקורה / תת קרקעית"
   ],
   [
    "storage_unit",
    "מחסן דיירים"
   ],
   [
    "ev_parking",
    "חניה עם עמדת טעינה"
   ]
  ]
 },
 {
  "key": "intl_real_estate",
  "label": "נדל״ן בחו״ל",
  "group": "נדל״ן",
  "icon": "🌐",
  "subs": [
   [
    "greece_cyprus",
    "יוון וקפריסין"
   ],
   [
    "europe",
    "אירופה"
   ],
   [
    "dubai_turkey",
    "דובאי וטורקיה"
   ],
   [
    "georgia",
    "גאורגיה והבלקן"
   ],
   [
    "usa",
    "ארה״ב"
   ]
  ]
 },
 {
  "key": "solar_energy",
  "label": "אנרגיה סולארית וטעינה",
  "group": "בית וגן",
  "icon": "☀️",
  "subs": [
   [
    "panels",
    "פאנלים"
   ],
   [
    "inverters",
    "מהפכים"
   ],
   [
    "batteries",
    "סוללות אגירה"
   ],
   [
    "ev_chargers",
    "עמדות טעינה לרכב"
   ],
   [
    "heaters",
    "דודי שמש"
   ]
  ]
 },
 {
  "key": "housewares",
  "label": "כלי בית, שטיחים ודקורציה",
  "group": "בית וגן",
  "icon": "🍳",
  "subs": [
   [
    "kitchenware",
    "כלי מטבח ואוכל"
   ],
   [
    "rugs",
    "שטיחים"
   ],
   [
    "curtains",
    "וילונות ותריסים"
   ],
   [
    "bedding",
    "מצעים ומגבות"
   ],
   [
    "decor",
    "דקורציה וקישוט"
   ]
  ]
 },
 {
  "key": "office_equipment",
  "label": "ציוד משרדי",
  "group": "עסקים ותעסוקה",
  "icon": "🖨️",
  "subs": [
   [
    "desks",
    "שולחנות וכיסאות משרדיים"
   ],
   [
    "copiers",
    "מכונות צילום והדפסה"
   ],
   [
    "pos",
    "קופות ונקודות מכירה"
   ],
   [
    "shredders",
    "מגרסות וציוד משרדי"
   ],
   [
    "partitions",
    "מחיצות ואחסון"
   ]
  ]
 },
 {
  "key": "auto_services",
  "label": "שירותי רכב ומוסכים",
  "group": "רכב ותחבורה",
  "icon": "🔩",
  "subs": [
   [
    "garage",
    "מוסכים ומכונאות"
   ],
   [
    "body",
    "פחחות וצבע"
   ],
   [
    "towing",
    "גרירה ודרך"
   ],
   [
    "detailing",
    "פוליש וציפוי"
   ],
   [
    "inspection",
    "בדיקות ורישוי"
   ]
  ]
 },
 {
  "key": "digital_services",
  "label": "שירותי דיגיטל ושיווק",
  "group": "שירותים",
  "icon": "🧑‍💻",
  "subs": [
   [
    "web",
    "אתרים ודפי נחיתה"
   ],
   [
    "marketing",
    "שיווק וקידום"
   ],
   [
    "branding",
    "מיתוג ועיצוב גרפי"
   ],
   [
    "apps",
    "אפליקציות ותוכנה"
   ],
   [
    "content",
    "תוכן ווידאו"
   ]
  ]
 },
 {
  "key": "childcare",
  "label": "שמרטפות, מטפלות וצהרונים",
  "group": "שירותים",
  "icon": "🧒",
  "subs": [
   [
    "babysit",
    "בייביסיטר"
   ],
   [
    "nanny",
    "מטפלת קבועה"
   ],
   [
    "family_daycare",
    "משפחתונים וגנים פרטיים"
   ],
   [
    "afterschool",
    "צהרונים"
   ],
   [
    "special_needs",
    "סייעות וצרכים מיוחדים"
   ]
  ]
 },
 {
  "key": "pet_services",
  "label": "שירותים לחיות מחמד",
  "group": "שירותים",
  "icon": "🐾",
  "subs": [
   [
    "vet",
    "וטרינרים"
   ],
   [
    "boarding",
    "פנסיון והוטלים"
   ],
   [
    "walking",
    "דוגווקרים וטיולים"
   ],
   [
    "training",
    "אילוף"
   ],
   [
    "grooming",
    "טיפוח ורחצה"
   ]
  ]
 }
];
