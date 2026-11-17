# Architecture

```
Browser (React PWA, Vercel) --HTTPS/WS--> FastAPI (Render/Railway) --> Postgres (Neon/Supabase) | SQLite (dev)
                                              |-- in-process worker + scheduler (agent_jobs queue in the DB)
                                              |-- optional Redis: wake-up signal only (REDIS_URL)
Sources: manual paste | Telegram webhook | RSS/Atom + JSON Feed adapters (Scout)
Pipeline: source -> extract (rules; optional LLM) -> dedup (exact + near) -> risk indicators -> score (+personalization) -> DB -> WebSocket/notification
```

| Spec agent | Implementation |
|---|---|
| Orchestrator | `jobqueue.py`: DB queue, atomic claim, retry with exponential backoff, dead-letter, dedupe key, `agent_events` history; `routes_v2.py` worker + scheduler |
| Scout | `scout.py` adapters (rss, jsonfeed), SSRF guard, robots.txt, size limits; Telegram webhook in `main.py` |
| NLP extraction | `extract.py` (rules, free); `llm.py` optional fill-in, validated, off by default |
| Filter / anti-spam | `scoring.risks`, `neardup.py`; indicators only, never accusations |
| Matching | `scoring.score` with user weights |
| Memory / RAG | `memory.py` + `neardup.embed` (local, free); optional pgvector (`pgvec.py`) |
| Notification | `notifications` table + WebSocket hub + optional WhatsApp Cloud API |

Cost model: everything above runs on free tiers. Paid features (OpenAI) are strictly opt-in: they need an API key in the environment AND an admin toggle.
Limits: the worker runs inside the API process (single instance); WebSocket hub is per-process. Scaling out needs a shared pub/sub (Redis) - not implemented.

## v3.1: running more than one instance
- Queue: on Postgres jobs are claimed with `FOR UPDATE SKIP LOCKED` (`app/scale.py`); jobs stuck in `running` past a 10-minute lease are re-queued by housekeeping (still bounded by `max_attempts`). The scheduler tick is idempotent (cursors + dedupe keys), so every instance may run it.
- Separate worker: run the API with `WORKER_ENABLED=0` and start `python -m app.worker` as another service (Railway: new service, same repo, start command `python -m app.worker`).
- Not solved by design: the **WebSocket hub is in-process**, so a browser connected to instance A will not receive a live push produced on instance B. The UI refreshes via `/api/notifications` (30 s) so nothing is lost, only latency. A cross-instance push needs Postgres LISTEN/NOTIFY or Redis pub/sub and was not added untested.
- Free reality check: free tiers (Render free, Railway trial credit) are effectively one small instance. The code is safe for N; the free hosting is the limit.

## v3.1 data flow additions
Webhooks: scheduler fan-out (per endpoint cursor) -> `webhook_deliver` jobs -> signed POST. Market brain: `app/market.py` (median/quartiles, deal verdict, weekly trend) over the user's own listings plus opt-in anonymised pool.

## v3.16 additions
Profile and learned memory: `brain_plus.py` (pure: insights, completeness, memory statements, recency bonus) + `routes_v9.py` (API) -> `agent_memory` through the existing `agent.remember` (so near-duplicates are skipped and the per-user cap still applies).
Data flow: listings the user saved / contacted / rejected -> `insights` (needs >= 2 agreeing listings) -> statements -> `agent.remember(kind="preference")` -> recalled by the agent with a bounded recency bonus.
Operations: `scripts/verify_wiring.py` (UI calls vs routes, router modules loaded) and `GET /api/admin/diagnostics`. Indexes: migration `a9b8c7d6e5f4`.

