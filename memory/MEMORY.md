# Tribal — Project Memory

## Stack
- Python 3.12 / FastAPI / SQLAlchemy 2 / APScheduler 3
- SQLite (dev), targeting MySQL 8 for SaaS
- Vanilla JS frontend (no bundler), served as static files
- Docker (python:3.12-slim image), docker-compose for local dev
- Deployed to DigitalOcean App Platform

## Key Files
- `app/main.py` — FastAPI app, auth middleware, lifespan (scheduler)
- `app/models.py` — SQLAlchemy models: Resource, ReminderLog, User
- `app/schemas.py` — Pydantic schemas (auth + resources)
- `app/auth.py` — JWT utilities (create/decode), bcrypt password hashing
- `app/dependencies.py` — `get_current_user` FastAPI dependency
- `app/routers/auth.py` — /auth/register, /auth/login, /auth/logout, /auth/me
- `app/routers/resources.py` — /api/resources CRUD
- `app/database.py` — SQLite engine, get_db dependency
- `static/login.html` — Self-contained login/register page
- `SAAS_ROADMAP.md` — Full multi-tenancy implementation plan

## Auth Implementation (done — branch: go-for-saas)
- Email + password accounts, bcrypt-hashed
- JWT stored in httpOnly cookie named `session` (7-day expiry)
- `JWT_SECRET` env var — auto-generates random secret if unset (warns about no persistence)
- Middleware in main.py: unauthenticated GET → redirect to /login; other methods → 401 JSON
- Exempt paths: `/login`, `/healthz`, `/auth/*`, `/static/*`
- Login page: two-tab (Sign In / Create Account) at `static/login.html`
- Header shows user display_name/email + Sign Out button

## Env Vars
- `JWT_SECRET` — **required for production** (stable sessions across restarts/replicas)
- Future (Phase 2): `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`

## SaaS Roadmap Phases
- Phase 0: Foundation cleanup (Alembic, MySQL, pydantic-settings) — partially done
- Phase 1: DB multi-tenancy (organizations, org_memberships, teams)
- Phase 2: Entra ID auth (replace email/password with Azure AD via fastapi-azure-auth)
- Phase 3: Admin panel
- Phase 4: DO deployment
- Phase 5: Full test suite
- Phase 6: Async notification queue (DB-backed)

## Development Notes
- App uses `Base.metadata.create_all()` (not Alembic yet) — new models auto-created
- Existing DB migration shim in `_run_migrations()` in main.py
- Tests in `tests/test_api.py` (20 tests, all passing per roadmap)
- `seed.py` exists for test data injection
