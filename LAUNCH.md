# KALIMA Launch Plan (hosted)

Product direction is a **hosted launch**. The code still runs local-only today
(loopback bind, one global API key, single-user data); this document is the
ordered list of what must change, with file pointers. Work proceeds top to
bottom: nothing in Phase B starts until Phase A is green.

## Ground truths (verified)

- Auth exists and is user-shaped: `users` + `auth_sessions(user_id)` in
  `app/storage/database.py`, PBKDF2-HMAC-SHA256 (210k), digest-only session
  tokens, `HttpOnly; SameSite=Lax` cookie (`app/auth/service.py`, `app/web.py`).
- Domain tables have **no `user_id`**: jobs, glossaries, library, translation
  memory, files. `/api/jobs` lists every in-memory job to anyone.
- Provider key is global (`config.yaml` → `openai.api_key`). The account portal
  already scaffolds the commercial shape: plans, credit packages, orders,
  API keys, marketplace (`app/account/service.py`, `/api/account/portal`).
- Billing math exists: `PRICING` + `app/jobs/estimate.py` + calibration budget
  guards. Spend is tracked per calibration session, not per user.
- Cookie has no `Secure` flag; no login rate-limiting (the old "lockout would
  be theatre" note applied to loopback-only and dies here).

## Phase A — multi-user correctness (must be first)

1. **User-scope every domain table.** Add `user_id` to jobs, glossaries,
   library books, translation memory, files, calibration sessions; migrate
   existing rows to the first user; scope every query. No new unscoped tables.
2. **Auth hardening.** Login rate-limit + lockout, `Secure` cookies, real CSRF
   tokens for cookie auth (or Bearer for API), password change + reset flow,
   session list/revoke in `/account`. See `roadmap` §2 (already shipped items
   stay).
3. **Server-side billing.** Provider keys move off the client: per-workspace
   keys or platform key + credit ledger. Wire calibration/estimate spend into
   per-user balances; enforce caps before dispatch (extend the existing budget
   guard, don't invent a second one).
4. **Origin policy.** Explicit CORS allowlist for the product domain (never
   `*`); keep Host checks; configurable bind host (env `KALIMA_HOST`, default
   loopback for dev).
5. **Upload integrity.** Fix double-upload (`upload_token` lookup in
   `POST /api/jobs`) — in production uploads cost bandwidth; add per-user
   storage quotas with the fix.

Acceptance: two users, two browsers — neither sees the other's books, jobs,
glossary, or spend; revoked session stops working; exhausted credits block
dispatch with a clear message. Full pytest green.

## Phase B — production deployment

1. **Serve the product.** Phase 6: backend serves React `dist/` (single origin,
   no CORS). Run `frontend/docs/audit_bundle.py` first; irreversible.
2. **TLS + proxy.** Reverse proxy (TLS termination, security headers) in front
   of the Python server; never expose stdlib HTTP directly. One-container
   deploy (Dockerfile) with `data/` on a volume.
3. **Backups + observability.** Scheduled SQLite backups (WAL-safe copy),
   structured-log shipping, uptime + error alerting, 5xx rate dashboard.
4. **Release hygiene.** `pyproject.toml`, versioned builds, secret scanning in
   CI, re-audit git history for keys, seeded demo account data.

Acceptance: fresh VPS → running product in <30 min from the docs; kill -9 the
container mid-book → resume works; restore-from-backup drill passes.

## Phase C — growth (after launch, not before)

- Object storage for books/outputs (paths stay behind `app/core/paths.py`).
- Postgres path if single-node SQLite becomes the bottleneck (WAL is fine
  until then — do not migrate prematurely).
- OAuth login, team workspaces, public sharing links with expiry.
- PWA + offline reading; mobile polish; help-center videos.

## What does NOT change

Thread-based engine, per-chunk resume, glossary snapshot + human approval,
adaptive rate limiting, Python-side sanitization, bilingual RTL UI, the
291→651-test discipline (`python -m pytest -q` before every PR), Conventional
Commits. The launch changes who the server serves — not how translation works.
