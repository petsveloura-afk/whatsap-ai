# פריסה ב-Railway

שני שירותים ומסד נתונים באותו פרויקט. אין צורך ב-Render, ואין "שינה" של השרת.

## 1. מסד נתונים
`New` → `Database` → `PostgreSQL`. Railway יוצר משתנה `DATABASE_URL` (הקוד מתאים אותו ל-psycopg אוטומטית).

## 2. שירות ה-API (backend)
`New` → `GitHub Repo` → שירות עם **Root Directory = `backend`** (הקובץ `backend/railway.json` כבר מגדיר Dockerfile ובדיקת `/api/health`).

משתנים:
| משתנה | ערך |
|---|---|
| `DATABASE_URL` | הפניה ל-Postgres: `${{Postgres.DATABASE_URL}}` |
| `JWT_SECRET` | מחרוזת אקראית של 32+ תווים (חובה) |
| `SUPER_ADMIN_EMAILS` | המייל שלך. **הירשם איתו מיד אחרי הפריסה הראשונה** |
| `APP_URL` | כתובת הפרונט, למשל `https://smart-sniper.up.railway.app` |
| `CORS_ORIGINS` | אותה כתובת (אפשר כמה, מופרדות בפסיק) |

המיגרציות רצות אוטומטית בכל הפעלה. `Settings` → `Networking` → `Generate Domain` כדי לקבל כתובת ציבורית.

## 3. שירות הפרונט (frontend)
שירות נוסף עם **Root Directory = `frontend`** (יש `frontend/Dockerfile` ו-`frontend/railway.json`).

משתנה: `VITE_API_URL` = כתובת ה-API מהשלב הקודם (בלי `/` בסוף). חשוב: המשתנה נקרא בזמן build, לכן אחרי שינוי יש לבצע Redeploy.
חלופה בלי build מחדש: לערוך את `frontend/public/config.js` ולהגדיר שם `window.__SNIPER_API__`.

## 4. בדיקה
1. `https://<api>/api/health` מחזיר `{"status":"ok"}`.
2. פתח את הפרונט, הירשם, ודא שנכנסת.
3. "Failed to fetch" בכניסה כמעט תמיד אומר ש-`VITE_API_URL` ריק או ש-`CORS_ORIGINS`/`APP_URL` לא כוללים את כתובת הפרונט. השרת מחזיר כעת כותרות CORS גם בשגיאות, כך שזה כבר לא מסתיר את הסיבה האמיתית.

## אבטחה (מה נוסף ב-v10)
- מדיניות סיסמה בשרת ובלקוח (10–72 בתים, לא נפוצה, לא רצף, לא מבוססת על האימייל).
- נעילת חשבון ל-15 דקות אחרי 8 ניסיונות כושלים; תגובה זהה (וזמן זהה) לחשבון שלא קיים.
- הגבלת הרשמות ל-8 לשעה לכל IP; שדה מלכודת נסתר לבוטים.
- טוקנים חתומים עם `iss`, `aud`, `typ`, `jti`, `iat`; טוקן מזויף, פג תוקף, `alg=none` או מסוג אחר נדחה.
- `/api/auth/logout-all` מבטל את כל ההתחברויות.
- הערה: הנעילה נשמרת בזיכרון השרת (מתאימה למופע אחד, כמו ברירת המחדל ב-Railway).
