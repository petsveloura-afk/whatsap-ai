# Smart Sniper AI v3 – core (checklist-tracked)
Run tests: `cd backend && pip install -r requirements.txt && pytest -q`
Run: `JWT_SECRET=<32+ chars> uvicorn app.main:app` → docs at /docs. Postgres needs `pip install psycopg[binary]`.

## Checklist
- [x] Auth (register/login/me, bcrypt, JWT 30 min)  - [x] Searches CRUD-lite (soft delete, pause/resume)
- [x] Extraction (rule-based HE/EN)  - [x] Dedup (per-user fingerprint)  - [x] Risk indicators  - [x] Weighted scoring (configurable)
- [x] Per-user isolation (tested)  - [x] Docker/compose/.env
- [x] RBAC (user/support/admin/super_admin), admin users+audit-logs, listing actions, data export/delete, Alembic initial migration  - [x] Refresh tokens (rotation + reuse detection), password reset (SMTP)  - [x] PayPal subscriptions (server-side checkout, verified+idempotent webhook, plan limits)  - [x] WhatsApp Cloud API notifications with consent  - [x] Request IDs, JSON logs, /api/admin/metrics, CORS allowlist  - [x] React/Vite PWA frontend (landing, auth, dashboard, live WS, admin users, billing)
- [ ] Remaining tables (images, embeddings...)
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

## Frontend (Vercel)
Root Directory `frontend`, env `VITE_API_URL=https://<railway-app>`; add that Vercel URL to backend `CORS_ORIGINS` and `APP_URL`. Local: `cd frontend && npm i && npm run dev` (proxies to :8000).

## Verification status
Tested automatically (SQLite, mocked externals): auth/refresh/reset, isolation, RBAC, Telegram webhook, WebSocket, PayPal webhook logic, WhatsApp hook. **Not tested against real services**: PayPal API calls, WhatsApp Cloud API, SMTP, Telegram, Postgres, Docker.


## Free deployment
See `docs/DEPLOYMENT-FREE.md` (GitHub + Vercel + Render + Neon/Supabase, all free tiers). `render.yaml` and `.github/workflows/keepalive.yml` are included.

## New in this round
- `POST /api/searches/parse` - natural-language search creation (rule-based, free).
- Near-duplicate detection (local trigram embeddings, no API).
- Login rate limiting (in-memory).

## Personal memory (free, local)
- Saving/rejecting a listing stores a per-user memory (local trigram embedding, no external AI).
- Future scores shift by at most +/-10 points, with the reason shown in `score_detail.personalization`.
- Controls: `GET /api/memory`, `PUT /api/memory/preferences`, `DELETE /api/memory`, `DELETE /api/memory/{id}`; included in `GET /api/me/export` and removed by `DELETE /api/me`.
- New Alembic revision `a7c1d2e3f4b5` (not yet executed - run `alembic upgrade head`).

## Round 4: Scout, worker, admin center, optional paid toggles
- Sources: `/api/sources` (RSS/Atom, JSON Feed) polled by an in-process worker (`WORKER_ENABLED=1`); queue in the DB (retry, dead-letter), optional Redis wake-up.
- 20 additional tables (`b1e2f3a4c5d6`) + optional pgvector revision (`c2f3a4b5d6e7`, no-op unless Postgres and `USE_PGVECTOR=1`).
- Admin: `/api/admin/overview|jobs|sources|actions|roles|system-settings`, `/api/agents/events`; maintenance mode and feature flags.
- Optional, OFF by default: LLM extraction and pgvector (admin toggles, need your own paid key / extension).
- UI: natural-language wizard, sources, notifications, memory/privacy, admin panel. Tests: `npm test` (Node), backend pytest incl. E2E.
- See `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/INTEGRATIONS.md`.

## v3.1 - growth, scale and security layer
Public API keys, signed webhooks, referrals, share links, market intelligence ("is this a good deal?"), weekly digest, extra Scout sources (JSON-LD, CSV, Reddit, public Telegram), shared rate limiting, self-hosted error tracking, multi-instance-safe queue + standalone worker, optional Postgres RLS. See `docs/GROWTH-MONETIZATION.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`.

## Railway notes
- `DATABASE_URL` must use the `postgresql+psycopg://` prefix.
- Alembic migrations were written for SQLite; `backend/migrations/env.py` converts Boolean `DEFAULT 0/1` to `false/true` when running on Postgres.
- After pushing a fix, make sure the new Railway deployment shows the latest commit (use a new commit, not Redeploy of an old one).
