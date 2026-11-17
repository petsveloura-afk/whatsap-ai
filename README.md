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

## v3.2 - smarter brain (free, local, no new dependencies)
- Extraction: ~70 Israeli cities (Hebrew/English, prefixes like ב/ל/מ), price formats (₪ before/after, אלף, מיליון, 5.200 thousands dot, $/€), rooms in words, area, floor, features, rent/sale, vehicles (brand/year/km/hand), phones (model/storage), negotiable/urgent, scam-signal flags. Original keys unchanged.
- Scoring: numeric keywords compare to extracted rooms (no more matching digits inside prices); negated words ("ללא תיווך") no longer trip an excluded "תיווך"; Hebrew or English search locations; human-readable `highlights` and a `label`.
- Risks: advance-payment / gift-card / pressure language, high mileage, needs-renovation (indicators, never proof).
- Natural-language search: price ranges ("בין 6000 ל-8000"), "70 אלף", "3.5 million", "מתחת ל", features ("עם חניה ומעלית"), plus an `understood` summary.
- UI: new glass/aurora design system (CSS only), light+dark, mobile friendly, reduced-motion aware.
- Tests: `backend/tests/test_smart_modules.py` (pure, no DB/network).
- New endpoints (additive, loaded in a try/except so the core API can't be affected): `GET /api/sources/suggest?search_id=`, `POST /api/sources/suggest/apply`, `POST /api/assistant`, `GET /api/listings/{id}/explain`, `GET /api/searches/{id}/report`.
- Free AI: `llm.py` supports Groq / Gemini / OpenRouter / Ollama free tiers through the OpenAI-compatible protocol (see `.env.example`). Off unless you add a free key AND enable the admin flag; the assistant falls back to local rules.
- Source discovery stays within Scout's guards (SSRF, robots.txt, size/time limits). No scraping of sites that forbid it.

## v3.3 - the agent (additive) + new design
- **Agent brain**: `POST /api/agent/chat`. A tool-calling loop (Gemini via its OpenAI-compatible endpoint, or any provider already set in `LLM_PROVIDER`). Tools: list/find/inspect listings, search report, create/update/pause searches, save/reject/contact a listing, notes, analyse pasted text, discover/add sources, remember/recall/forget. All tools are scoped to the logged-in user; there is **no delete tool**; every write is reported back to the UI.
- **Memory**: long-term facts/preferences/goals/summaries (`agent_memory`) + short chat history (`agent_messages`, rolled up into a summary when it grows). `GET/POST/DELETE /api/agent/memory`, `GET/DELETE /api/agent/history`. Covered by `/api/me/export/full` and `DELETE /api/me`. Respects the existing personalization switch.
- **Switch**: needs `GEMINI_API_KEY` (or another provider key) AND the admin flag `llm_extraction`. Otherwise the same chat works on local rules, so nothing breaks. `GET /api/agent/status` shows which mode is active.
- **Safety**: listing text and memory are treated as untrusted data in the system prompt; 40 messages/user/hour; 6 tool rounds max per message.
- New migration `f4b5c6d7e8a9` (runs automatically on deploy). Tests: `backend/tests/test_agent.py` (no network).
- **Design**: `frontend/src/styles.css` rewritten (same class names); the previous file is kept as `styles.v3.2.css` (not imported). New: `frontend/src/agent.tsx`.

### v3.3 discovery
- `POST /api/agent/discover {search_id, query?, limit}`: web search via Brave/Tavily (`BRAVE_API_KEY` or `TAVILY_API_KEY`), results scored by the normal pipeline; 20/hour/user; 503 when no key. We store only title, snippet and link and never fetch result pages.
- `POST /api/listings/ingest-bulk {search_id, text}`: up to 30 pasted listings separated by `---` or blank lines.
- Agent tools `web_search_import` and `ingest_many` use the same code. `GET /api/agent/status` now reports `web_search`.
- Agent provider: a `GEMINI_API_KEY` wins over `LLM_PROVIDER`; set `AGENT_PROVIDER=groq` to force otherwise. Groq defaults to `llama-3.3-70b-versatile` for the agent.

## v3.4 - New interface + contact actions
- New "Neon Instrument" UI: sidebar navigation (bottom bar on phones), KPI cards, ring gauges, glass surfaces, dark/light themes.
- Every opportunity now shows ways to reach the owner: call, WhatsApp (pre-filled message), e-mail, Telegram, and a link to the source ad, plus copy-details.
- Backend: `app/contacts.py` extracts phones/e-mails/chat links from the ad text you already stored (no scraping); `GET /api/listings` keeps all old fields and adds title, summary, raw_text, contact, highlights, source_url, created_at. Web-discovery results also carry title and contact.
- No existing panel, endpoint or table was removed.

## v3.7 - Free brains (additive)
- `app/brains.py`: one router for 13 free AI providers (Gemini, Groq, Cerebras, OpenRouter, Mistral, GitHub Models, SambaNova, NVIDIA, Hugging Face, Cloudflare, Ollama, custom OpenAI-compatible, OVH key-less) with **several keys per provider**, round-robin rotation, cooldowns (rate limit / daily quota / bad key / retired model) and automatic failover across keys, models and providers. The agent, the LLM extraction and the assistant polish all use it.
- Free-only: OpenAI is never used unless `LLM_PROVIDER=openai` or `BRAINS_ALLOW_PAID=1`. Extraction is capped per day (`BRAINS_EXTRACT_DAILY`), cached, and skipped when the rules already found every field.
- `app/discovery.py`: web search over Tavily, Serper, Brave, Exa, Jina, Google CSE and SearXNG with the same key pool; results are merged and de-duplicated.
- `GET /api/admin/brains`, `POST /api/admin/brains/test` and the new **Admin > Brains** tab. `GET /api/agent/status` adds `brains` and `web_searches`. Keys are never returned.
- Setup guide (Hebrew): `docs/FREE-BRAINS.md`. Tests: `backend/tests/test_brains.py` (no network).

## v3.12 - Model discovery (additive)
- Problem fixed: Google and Groq retired the model names that were hard-coded (`gemini-2.5-flash`, `llama-3.3-70b-versatile`), so "בדוק חיבורי AI" showed HTTP 404 even with valid keys.
- `app/brains.py` now asks every provider which models the key can really use (`GET <base>/models`), drops non-chat models (embeddings, speech, image, guard), ranks the rest (newest and strongest first, stable `-latest` aliases preferred, previews last) and refreshes the list every 6 hours. A retired name fixes itself; no code change needed.
- When a 404 message names the replacement ("update your code to use models/gemini-3.8-flash") it is learned and tried immediately.
- The static lists stay as the fallback (two stable Gemini aliases and two Groq models were added). `<NAME>_MODEL=...` still overrides everything. `BRAINS_DISCOVER=0` turns discovery off.
- Free-only: OpenRouter discovery keeps only `:free` models; OpenAI (paid) and Cloudflare are never queried.
- "בדוק חיבורי AI" now tries the next model when one is retired and shows what was tried. New button **רענן רשימת מודלים** (`POST /api/admin/brains/models/refresh`, no model quota used). The agent picks the best discovered Gemini model instead of a fixed name.
- Tests: `backend/tests/test_brains_discovery.py` (no network).

## v3.13 - Pro toolkit and Scan+ (additive)
- 30+ sellable features that cost nothing to run, grouped as scan and automation, listing analysis (fraud check, fair price, negotiation helper, comparison, duplicate clusters, smart tags, viewing checklist), AI (analyst, translation), calculators (mortgage, affordability, purchase tax 2026, yield, vehicle cost, used price), CRM (pipeline, reminders, alert rules, broker clients), reports (market report, weekly brief, CSV, branded deal sheet, share pack, 4-language message templates).
- Plans: starter < pro < vip, each tool has a monthly free trial for lower plans (the upsell hook). `PRO_OPEN=1` opens everything for testing. See `docs/PRO-TOOLKIT.md`.
- Scan+ (`/api/pro/scan/plus`): query expansion, re-ranking, junk filtering, per-query report, engine advisor and a VIP auto-scan. Free engines only, title + snippet + link only.
- Backend: `app/toolkit.py` and `app/scanplus.py` (pure, tested), `app/routes_v7.py` (routes + scheduler ticks), registered at the bottom of `main.py` in try/except. No new tables.
- Frontend: new tab "כלי פרו" (`src/pro.tsx`, `src/styles.pro.css`).
- Tests: `backend/tests/test_toolkit.py` (no deps) and `backend/tests/test_v7_api.py` (CI).
