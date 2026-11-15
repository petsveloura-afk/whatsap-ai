# פריסה חינמית (ללא עלות)

כל הרכיבים כאן ניתנים לשימוש בחבילה החינמית של הספקים. מגבלות החבילות החינמיות משתנות מעת לעת - בדוק אותן באתרי הספקים לפני הפריסה.

| רכיב | שירות | הערה |
|---|---|---|
| קוד | GitHub | repo פרטי או ציבורי, CI ב-GitHub Actions |
| Frontend | Vercel (Hobby) | תיקיית `frontend`, מוגדר ב-`vercel.json` |
| Backend | Render (Free web service) | `render.yaml`; נרדם כשאין תנועה - ראה keepalive |
| מסד נתונים | Neon או Supabase (Free) | רק מחרוזת חיבור Postgres; ללא pgvector |
| תור/Workers | בתוך השרת | אין Redis - אין עלות |
| AI | חוקים מקומיים + דמיון מקומי | ללא OpenAI - אין עלות |

## שלבים
1. צור repo ב-GitHub ודחוף: `git remote add origin <url> && git push -u origin main`.
2. צור מסד Postgres חינמי (Neon/Supabase) והעתק את ה-connection string.
3. Render: New > Blueprint > בחר את ה-repo. מלא `DATABASE_URL`, `SUPER_ADMIN_EMAILS`, `CORS_ORIGINS`, `APP_URL`. המיגרציות רצות אוטומטית עם עליית ה-Docker.
4. Vercel: Import את ה-repo, Root Directory = `frontend`, והגדר את משתנה כתובת ה-API כפי שמופיע ב-README.
5. GitHub: Settings > Variables > הוסף `API_URL` לכתובת ה-Render כדי להפעיל את `keepalive.yml`.
6. אופציונלי (רק אם תרצה בעתיד): PayPal, WhatsApp, SMTP, Telegram - ללא ההגדרות האלה הם פשוט מוצגים כלא זמינים.

## מה לא נבדק
הקבצים כאן לא נפרסו בפועל. לא הורצו Docker, Postgres, Render או Vercel.
