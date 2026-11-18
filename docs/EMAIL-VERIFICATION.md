# אימות אימייל (v3.17)

- בהרשמה נשלח קישור חד-פעמי (תקף 24 שעות). במסד נשמר רק hash של הטוקן.
- **האכיפה פעילה רק כש-`SMTP_HOST` מוגדר.** בלי SMTP אי אפשר לשלוח מייל, ולכן לא נדרש אימות ואף משתמש לא ננעל.
- לביטול האכיפה גם כש-SMTP מוגדר: `REQUIRE_EMAIL_VERIFICATION=0`.
- עד האימות חסומה רק התחלת תשלום (הזמנה וגם מנוי מתחדש). כניסה ושאר המערכת ממשיכות לעבוד.
- משתמשים קיימים מסומנים כמאומתים במיגרציה. admin ו-super_admin פטורים.
- שליחה חוזרת: המתנה של דקה בין בקשות, עד 5 בשעה. קישור ישן מפסיק לעבוד כשמתקבל חדש.
- נדרש: `APP_URL` עם כתובת הפרונט, כי הקישור במייל הוא `APP_URL/?verify=...`.
- API: `POST /api/auth/verify-email`, `POST /api/auth/resend-verification`; `GET /api/auth/me` מחזיר `email_verified` ו-`verification_required`.

## עדכון v3.18: שליחה דרך HTTPS וחסימה מלאה עד אימות

- **Railway בחבילות Free/Trial/Hobby חוסם SMTP (פורטים 25/465/587).** לכן עם `SMTP_HOST` המייל לא יוצא. הפתרון: `RESEND_API_KEY` (מפתח Sending access) ו-`MAIL_FROM=Smart Sniper <no-reply@supercoder.agency>`. השליחה היא HTTPS בפורט 443. כשהמפתח מוגדר הוא קודם ל-SMTP.
- האכיפה פעילה כשיש `RESEND_API_KEY` או `SMTP_HOST` (ובלי `REQUIRE_EMAIL_VERIFICATION=0`).
- **חסימה מלאה:** משתמש לא מאומת מקבל 403 על כל קריאת API חוץ מ-`/api/auth/me`, שליחה חוזרת והתנתקות. ה-WebSocket נסגר. בפרונט מוצג מסך אימות במקום האפליקציה.
- כשל בשליחה נרשם ב-Deploy Logs: `verification mail to ... FAILED`.
