# Smart Sniper AI v3 – core (checklist-tracked)
Run tests: `cd backend && pip install -r requirements.txt && pytest -q`
Run: `JWT_SECRET=<32+ chars> uvicorn app.main:app` → docs at /docs. Postgres needs `pip install psycopg[binary]`.

## Checklist
- [x] Auth (register/login/me, bcrypt, JWT 30 min)  - [x] Searches CRUD-lite (soft delete, pause/resume)
- [x] Extraction (rule-based HE/EN)  - [x] Dedup (per-user fingerprint)  - [x] Risk indicators  - [x] Weighted scoring (configurable)
- [x] Per-user isolation (tested)  - [x] Docker/compose/.env
- [x] RBAC (user/support/admin/super_admin), admin users+audit-logs, listing actions, data export/delete, Alembic initial migration  - [ ] Refresh tokens/password reset  - [ ] Remaining ~18 tables
- [x] Pipeline agents with real telemetry (/api/agents), WebSocket events (/ws, per-user), Telegram webhook with chat-ownership linking  - [x] Railway/GitHub config + CI
- [ ] LLM extraction, embeddings/pgvector  - [ ] Redis workers, Scout source adapters (URL feeds)
- [ ] WhatsApp, PayPal (need credentials)  - [ ] React frontend/PWA/landing/admin UI  - [ ] Observability

## Deploy: GitHub + Railway
1. `git remote add origin <your repo> && git push -u origin main` (CI runs tests).
2. Railway → New Project → Deploy from GitHub repo → set **Root Directory = backend**.
3. Add the Postgres plugin (sets `DATABASE_URL`; `postgres://` URLs are normalized).
4. Variables: `JWT_SECRET` (32+ random chars), `SUPER_ADMIN_EMAILS`, `TELEGRAM_WEBHOOK_SECRET`.
5. Telegram: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook" -d url=https://<app>/api/integrations/telegram/webhook -d secret_token=<TELEGRAM_WEBHOOK_SECRET>`
Migrations run automatically on start. Run a single worker (WebSocket hub and agent stats are in-process; they reset on restart).
Cost note: Railway gives trial credit, not permanent free hosting. A free alternative using the same Dockerfile: Render free web service + Supabase free Postgres (the free web service sleeps when idle).
