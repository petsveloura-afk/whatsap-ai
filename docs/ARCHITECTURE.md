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
