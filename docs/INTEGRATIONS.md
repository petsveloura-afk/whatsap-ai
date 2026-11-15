# Integrations
- **Telegram**: set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`; register the webhook with the secret; send `/link <code>` in the chat. A bot cannot read chats it was not added to.
- **RSS/Atom / JSON Feed (Scout)**: add under Sources. Polls every `interval_minutes` (15-1440) via the worker.
- **PayPal**: `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_WEBHOOK_ID`, `PAYPAL_PLAN_PRO`, `PAYPAL_PLAN_VIP`, `PAYPAL_BASE`. PayPal fees apply to your transactions.
- **WhatsApp**: official Cloud API only (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TEMPLATE`) with explicit user consent. QR pairing is not supported (unofficial, may violate terms).
- **SMTP**: `SMTP_*` for password reset mail.
- **OpenAI (optional, paid)**: `OPENAI_API_KEY` + admin toggle `llm_extraction`.
- **pgvector (optional)**: Postgres with the extension; `USE_PGVECTOR=1` before migrating, then the admin toggle `pgvector`; query with `GET /api/memory/similar?q=`.
- **Redis (optional)**: `REDIS_URL`; used only to wake the worker.
