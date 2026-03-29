# Tribal — Claude Code Context

Credential lifecycle management: TLS certs, API keys, SSH keys. FastAPI backend + Vue 3 SPA, single container, MySQL.

## Commands

```bash
docker compose up --build          # start full stack (builds frontend into image)
docker compose run --rm --no-deps tribal python -m pytest tests/ -v  # run tests
cd frontend && npm run dev         # hot-reload frontend at :5173 (proxies API to :8000)
npm run typecheck                  # vue-tsc --noEmit
```

## Layout

```
app/
  main.py          — FastAPI app, auth middleware, lifespan (starts scheduler)
  models.py        — SQLAlchemy models
  schemas.py       — Pydantic request/response schemas
  dependencies.py  — get_current_user (session cookie + API key)
  scheduler.py     — APScheduler jobs (expiry reminders, cert refresh, review reminders)
  audit.py         — audit log helpers
  routers/
    auth.py        — /auth/register, /login, /logout, /me
    resources.py   — /api/resources CRUD + /api/identify (provider introspection)
    keys.py        — /api/keys (user API key management)
    admin.py       — /admin/* (users, settings, teams, audit log, reports)
  providers/       — credential provider plugins (auto-discovered)
    __init__.py    — registry: list_providers(), identify(key), find_by_name(name), introspect(key)
    base.py        — Provider ABC + IntrospectionResult dataclass
frontend/src/
  views/           — page components (Overview, Resources, Admin, Docs)
  stores/          — Pinia stores
  api/             — typed API client helpers
tests/             — pytest, SQLite in-memory, real login flow (no mocks)
alembic/           — DB migrations
terraform/         — DigitalOcean App Platform infra
```

## Auth

Dual auth via middleware (`main.py`). Exempt paths: `/auth/`, `/static/`, `/login`, `/healthz`, `/metrics`.

- **Session cookie**: JWT in `session` httpOnly cookie, `sub` = user_id, 7-day expiry.
- **API key**: `Authorization: Bearer tribal_sk_...` — SHA256 hash stored in DB, filtered by `revoked_at.is_(None)`.
- `request.state.auth_via` is set to `"ui"` or `"api"` — used in audit log detail JSON.
- Unauthenticated GET → 303 redirect to `/login`; other methods → 401 JSON.

## Key Patterns

**Soft deletes**: Resources are never hard-deleted. `resource.deleted_at` is set to UTC now. All queries use the `_active()` helper which filters `deleted_at.is_(None)`. Admins can recover deleted resources.

**Singleton Team**: One `Team` row per instance. When `AdminSettings.org_name` is updated, the `Team.name` must also be updated (they are separate, unlinked rows — see `admin.py`). Team is auto-assigned to resources that don't specify one.

**AdminSettings singleton**: Always accessed via `_get_or_create_settings()` (id=1). Stores `reminder_days` as JSON array, `notify_hour` (0–23 UTC), webhook URLs, and feature flags.

**Scheduler sessions**: Scheduler jobs create their own `SessionLocal()` — they run outside the request cycle so FastAPI dependency injection is unavailable.

**Reminder idempotency**: `ReminderLog` table deduplicates by (resource_id, expiration_date, days_before, reminder_type). Types are `"expiry"` and `"review"`. Overdue admin alerts use `days_before = -1`.

**Audit logging**: `_audit()` helper catches its own exceptions so auditing never breaks the main request flow. Detail field is a JSON string.

**Resource fields (non-obvious)**:
- `does_not_expire` — skip expiry reminders; resource is still tracked
- `auto_refresh_expiry` — daily job re-checks TLS cert at `certificate_url` and updates `expiration_date`
- `last_reviewed_at` — drives review cadence reminders (separate from expiry)

## Provider System

`GET /api/providers` — lists all registered provider names.
`POST /api/identify` — identifies a key and optionally introspects it.

```json
{ "key": "...", "introspect": true }                    // auto-detect by pattern
{ "key": "...", "introspect": true, "provider": "Fastly" }  // manual provider (no pattern)
```

Providers with no distinctive key prefix (Cloudflare, Fastly, PagerDuty, Vercel) require `provider` to be set explicitly — pattern matching returns `matched=false` for these. Use `find_by_name()` in the registry to resolve them.

Adding a provider: create `app/providers/<name>.py` with a `Provider` subclass — auto-discovered at startup, no registration needed.

## Tests

- SQLite in-memory DB; `app.dependency_overrides[get_db]` replaces the session.
- Tests call real `/auth/login` to get a session cookie — auth is not mocked.
- Admin user is seeded in the fixture using `hash_password()`.

## OSS Notes

- Specs and roadmap are maintained outside the repo. Do not create plan/roadmap `.md` files in the repo root.
- The active roadmap is summarised in `README.md#roadmap`.
- MIT licensed.
