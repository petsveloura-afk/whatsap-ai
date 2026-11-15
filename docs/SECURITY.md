# Security and threat model

| Threat | Mitigation | Status |
|---|---|---|
| Credential stuffing | bcrypt, 10 attempts/5 min per IP+email | implemented, in-memory (per instance) |
| Token theft/reuse | 30 min access JWT, rotating refresh tokens with reuse detection | implemented |
| Cross-tenant leakage | every query filtered by `user_id`; memory and events per user | implemented + tests |
| Privilege escalation | server-side RBAC; only super_admin changes roles; audit + admin_actions | implemented |
| SSRF via user URLs | http(s) only, ports 80/443, no credentials, all resolved IPs must be public, redirects re-validated, 1 MB cap | implemented. Residual: DNS rebinding between check and connect |
| XML bombs / XXE | DTD/entities rejected before parsing | implemented |
| Fake payments | activation only from signature-verified PayPal webhook, idempotent | implemented, not tested against real PayPal |
| Telegram spoofing | webhook secret + `/link` ownership code | implemented |
| Abuse of scraping | only user-supplied feeds, robots.txt respected, no auth/anti-bot bypass | implemented |
| LLM data exposure | off by default; only listing text sent; output validated, fill-only | implemented |
| Secrets | env vars only; none in frontend | implemented |

Not done: CSRF (tokens are in Authorization headers, not cookies), Row-Level Security in Postgres, encrypted storage of integration credentials (none are stored), automated backups (use the DB provider's), error tracking service, distributed rate limiting.

## v3.1 additions
- **Security headers** on every response (nosniff, frame deny, no-referrer, HSTS on https, COOP) + `X-Request-ID` for tracing.
- **Shared rate limit**: on Postgres the login limiter is stored in the database (`rate_hits`), so it holds across instances. Falls back to memory if the DB is unreachable (availability over strictness; logged).
- **Error tracking**: `error_events` groups unhandled errors by fingerprint, scrubs tokens/passwords/API keys, visible at `GET /api/admin/errors`. Optional Sentry forwarding only if you set `SENTRY_DSN` and install `sentry-sdk` (Sentry free tier exists; off by default).
- **API keys** are shown once and stored as SHA-256; scoped (`read`, `ingest`), revocable, quota per plan per 24h.
- **Outbound webhooks**: https only, SSRF-guarded on every delivery, no redirects, HMAC-SHA256 signature over `<timestamp>.<body>` (verify and reject timestamps older than 5 minutes), auto-disable after 15 consecutive failures.
- **Share links**: random token (hash stored), expiring (max 30 days), revocable, sanitised view (no raw text, contact details, notes or user id).
- **Market pool** is opt-in per user and stores only category/area/rooms/price with no identity; pooled statistics are refused below 5 samples.
- **Account deletion** now removes rows from every table with a `user_id` column (FK-safe), and `GET /api/me/export/full` exports all of them (secrets and hashes excluded).

### Postgres Row-Level Security (defence in depth)
Migration `d3a4b5c6e7f8` creates an `user_isolation` policy on every user-owned table (`ENABLE`, not `FORCE`). **It does nothing until you opt in**, because table owners bypass RLS:
1. Create a non-owner role for the app: `CREATE ROLE app_user LOGIN PASSWORD '...'; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_user;` (run migrations with the owner URL, run the API with the `app_user` URL).
2. Set `RLS_ENFORCE=1` on the API.
Then each authenticated request sets `app.user_id` for its transaction and Postgres itself refuses cross-user reads/writes. Auth, admin, webhook and public-API routes and the worker run with bypass on (they filter in code). **Test this on a staging database first**; it was written without a Postgres available to run it.
