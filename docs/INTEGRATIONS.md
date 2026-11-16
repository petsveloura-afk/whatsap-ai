# Integrations
- **Telegram**: set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`; register the webhook with the secret; send `/link <code>` in the chat. A bot cannot read chats it was not added to.
- **RSS/Atom / JSON Feed (Scout)**: add under Sources. Polls every `interval_minutes` (15-1440) via the worker.
- **PayPal**: `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_WEBHOOK_ID`, `PAYPAL_PLAN_PRO`, `PAYPAL_PLAN_VIP`, `PAYPAL_BASE`. PayPal fees apply to your transactions.
- **WhatsApp**: official Cloud API only (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TEMPLATE`) with explicit user consent. QR pairing is not supported (unofficial, may violate terms).
- **SMTP**: `SMTP_*` for password reset mail.
- **AI models (free)**: see `docs/FREE-BRAINS.md` (Gemini, Groq, Cerebras, OpenRouter, ... with failover). OpenAI is paid and only used if you opt in with `LLM_PROVIDER=openai`.
- **pgvector (optional)**: Postgres with the extension; `USE_PGVECTOR=1` before migrating, then the admin toggle `pgvector`; query with `GET /api/memory/similar?q=`.
- **Redis (optional)**: `REDIS_URL`; used only to wake the worker.

## v3.1 source kinds (`POST /api/sources`, `kind`)
`rss`, `jsonfeed` (as before) plus `jsonld` (schema.org Product/Offer/RealEstateListing/Vehicle... embedded in a page), `csv` (header: title,description,price,url,image[,currency]), `reddit` (a subreddit's `.../new.json`), `tgpublic` (public channel preview `https://t.me/s/<channel>`).
All go through the same guards: SSRF check, robots.txt, 1 MB cap, 15 s timeout, 30 items per poll. There is intentionally **no scraper for sites that forbid it** (e.g. Yad2/Facebook Marketplace): use their official feeds/exports, or paste/ingest listings yourself. Check each site's terms before adding it as a source.

## Public API (sell/integrate)
Header `X-API-Key: ssk_...`. `GET /api/public/v1/listings?limit&min_score`, `POST /api/public/v1/ingest {search_id,text,url}`, `GET /api/public/v1/usage`. Quota/24h: starter 200, pro 5,000, vip 50,000, +100 per referral (cap 20).
Webhook payload: `{"event":"listing.new","listing":{...},"sent_at":"..."}`, header `X-Sniper-Signature: t=<unix>,v1=<hex hmac-sha256 of "<t>.<body>">`.
