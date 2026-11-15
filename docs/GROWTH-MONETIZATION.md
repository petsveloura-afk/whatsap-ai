# Free growth tools you can sell (v3.1)
Everything below costs you nothing to run; you decide what to charge. Plans already exist (starter 0 / pro 99 / vip 149 ILS via PayPal).

| Feature | What the customer gets | How you can package it |
|---|---|---|
| Public API + keys | Pull/ingest listings from Zapier, Make, Sheets, their own CRM | Include API access only in pro/vip (raise `PLAN_DAILY_QUOTA` in `app/growth.py`) |
| Signed webhooks | Real-time push of new matches into any tool | "Automations" add-on for pro/vip |
| Market brain | Median/quartile price, "good deal / fair / above market / suspiciously low", weekly trend | The headline "know if it's a deal" feature |
| Weekly digest | Email summary of the best matches | Retention; free tier teaser |
| Share links | Send a sanitised listing page to a partner/spouse/client | Viral loop |
| Referrals | +100 API requests/day per referred friend | Free acquisition |
| Extra sources | JSON-LD pages, CSV, Reddit, public Telegram channels | Per-search source slots |

## Honest constraints
- Free hosting sleeps/limits; selling a paid service on free tiers means expect downtime. Upgrade hosting once revenue arrives.
- You are responsible for lawful data use: only ingest sources that allow it, comply with the Israeli Privacy Protection Law and anti-spam rules for WhatsApp/email, and keep a privacy policy that mentions the opt-in market pool.
- The deal verdict is a statistical indicator, not advice or proof of fraud; the UI and docs say so.
- Nothing here predicts revenue.

## Operating checklist
1. Deploy per `docs/DEPLOYMENT-FREE.md`. 2. Set `SUPER_ADMIN_EMAILS`. 3. Watch `Admin > Errors` (`/api/admin/errors`) and `/api/admin/growth`. 4. Turn on SMTP only if you want the digest.
