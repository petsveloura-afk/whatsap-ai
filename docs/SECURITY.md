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
