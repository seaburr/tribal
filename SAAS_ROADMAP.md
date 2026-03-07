# Tribal — SaaS Roadmap

This document captures the full technical plan for evolving Tribal from a single-tenant internal tool into a multi-tenant SaaS application. Implementation will be done incrementally, with Claude handling code, tests, and migrations at each phase.

---

## Target Stack

| Layer | Technology |
|---|---|
| Backend | Python / FastAPI (unchanged) |
| Database | MySQL 8 (replacing SQLite) |
| ORM / Migrations | SQLAlchemy 2 + Alembic |
| Auth | Microsoft Entra ID (Azure AD) via `fastapi-azure-auth` |
| Async task queue | DB-backed notification queue (swappable to Celery + Redis later) |
| Frontend | Vanilla JS (unchanged) |
| Deployment | DigitalOcean App Platform |
| Managed DB | DigitalOcean Managed MySQL |
| TLS / CDN | Handled by DO App Platform (automatic) |

## Cost Target

Goal: HA deployment under $40/mo.

| Resource | Spec | Est. Cost |
|---|---|---|
| DO App Platform (2 instances) | Basic — 512MB RAM, 0.5 vCPU each | ~$10/mo |
| DO Managed MySQL | Basic — 1GB RAM, 1 vCPU, 10GB storage | ~$15/mo |
| DO Managed MySQL standby node | Read replica / failover | ~$15/mo |
| **Total (no broker)** | | **~$40/mo** |

No separate broker infrastructure is needed in the initial SaaS phase — the DB-backed notification queue (see Phase 6) runs on the existing MySQL instance. When throughput demands it, swap the queue backend for DO Managed Redis + Celery without changing the task interface.

---

## Implementation Phases

### Phase 0 — Foundation (pre-SaaS cleanup)

Before adding multi-tenancy, stabilize the existing codebase:

- [x] Add `pytest` test suite for all existing API routes *(done — Iteration 5)*
- [x] Add `/healthz` endpoint *(done)*
- [ ] Replace `ALTER TABLE` migration shim with proper Alembic setup
- [ ] Swap SQLite → MySQL locally (Docker Compose dev environment)
- [ ] Move all config (DB URL, scheduler time, etc.) to environment variables via `pydantic-settings`
- [ ] Add structured logging (JSON, for DO log drain compatibility)
- [ ] Write a `docker-compose.dev.yml` that spins up MySQL + the app for local dev

**Deliverables:** All existing functionality green under pytest; app runs against MySQL locally.

---

### Phase 1 — Database: MySQL + Alembic

**Schema changes** (Alembic migrations, one per table):

```
organizations
  id                BIGINT PK AUTO_INCREMENT
  name              VARCHAR(255) NOT NULL
  slug              VARCHAR(64) UNIQUE NOT NULL   -- URL-friendly identifier
  entra_tenant_id   VARCHAR(128) UNIQUE           -- null until Entra is linked
  timezone          VARCHAR(64) NOT NULL DEFAULT 'UTC'
  created_at        DATETIME NOT NULL DEFAULT NOW()

users
  id                BIGINT PK AUTO_INCREMENT
  entra_oid         VARCHAR(128) UNIQUE NOT NULL   -- Azure object ID
  email             VARCHAR(255) NOT NULL
  display_name      VARCHAR(255)
  created_at        DATETIME NOT NULL DEFAULT NOW()

org_memberships
  org_id            BIGINT FK → organizations.id
  user_id           BIGINT FK → users.id
  role              ENUM('admin', 'member', 'read_only') NOT NULL DEFAULT 'member'
  joined_at         DATETIME NOT NULL DEFAULT NOW()
  PRIMARY KEY (org_id, user_id)

-- Role definitions:
--   admin     : full CRUD, manage members/teams, access admin panel, configure notifications
--   member    : create, edit, delete resources (subject to org deletion policy)
--   read_only : view resources and calendar only; no create/edit/delete

teams
  id            BIGINT PK AUTO_INCREMENT
  org_id        BIGINT FK → organizations.id NOT NULL
  name          VARCHAR(255) NOT NULL
  created_at    DATETIME NOT NULL DEFAULT NOW()

team_memberships
  team_id       BIGINT FK → teams.id
  user_id       BIGINT FK → users.id
  PRIMARY KEY (team_id, user_id)

org_notification_settings
  org_id              BIGINT PK FK → organizations.id
  reminder_days       JSON NOT NULL DEFAULT '[30, 14, 7, 3]'  -- admin-configurable cadence
  notify_time         TIME NOT NULL DEFAULT '09:00:00'         -- local time to send (org timezone)
  timezone            VARCHAR(64) NOT NULL DEFAULT 'UTC'
  digest_mode         BOOLEAN NOT NULL DEFAULT FALSE           -- single daily digest vs per-resource
  allow_member_delete BOOLEAN NOT NULL DEFAULT TRUE            -- admins can lock deletion to admins only
  purge_after_days    INT NOT NULL DEFAULT 30                  -- days after soft-delete before hard purge
  updated_at          DATETIME NOT NULL DEFAULT NOW()

resources   (add/modify columns on existing table)
  + org_id          BIGINT FK → organizations.id NOT NULL
  + team_id         BIGINT FK → teams.id NULL
  + created_by      BIGINT FK → users.id NULL
  + deleted_at      DATETIME NULL DEFAULT NULL   -- soft delete; NULL = active

-- All queries filter WHERE deleted_at IS NULL by default.
-- Deletion sets deleted_at = NOW() and enqueues a notification_task for the deletion Slack message.
-- A scheduled job hard-purges resources WHERE deleted_at <= NOW() - purge_after_days.
-- Admin panel shows soft-deleted resources within the purge window with a Restore button.

audit_logs
  id            BIGINT PK AUTO_INCREMENT
  org_id        BIGINT FK → organizations.id NOT NULL
  user_id       BIGINT FK → users.id NULL    -- null for system actions
  resource_id   BIGINT FK → resources.id NULL
  action        VARCHAR(64) NOT NULL          -- e.g. 'resource.create', 'resource.delete'
  detail        JSON                          -- before/after diff or freeform context
  created_at    DATETIME NOT NULL DEFAULT NOW()
  INDEX (org_id, created_at)
  INDEX (resource_id)
```

**All existing API queries** gain a mandatory `WHERE org_id = :current_org AND deleted_at IS NULL` filter applied by a FastAPI dependency — no cross-org leakage possible by construction.

**Testing:** Unit tests for each migration (forward + rollback). Integration tests confirming org isolation (resource created in org A is not visible to org B).

---

### Phase 2 — Authentication: Entra ID

**Backend:**

```
pip install fastapi-azure-auth
```

- Register a Tribal app in Entra: define API scope `tribal.access`
- Add `AzureAuthorizationCodeBearer` middleware to FastAPI
- On first authenticated request, auto-provision the user row in `users`
- Org membership provisioned via invite flow (see Phase 3) or Entra group mapping

**FastAPI dependency chain:**
```
get_current_user(token) → User
  └─ get_current_org_membership(user, org_id_from_path_or_header) → OrgMembership
       └─ require_role("admin" | "member" | "read_only") → OrgMembership (raises 403 if insufficient)
```

Route-level enforcement:
- `read_only` and above: GET routes
- `member` and above: POST, PUT (resource create/edit)
- `admin` only: DELETE, all `/admin/*` routes, notification settings

Every protected route declares which dependency it needs. This keeps auth logic out of business logic.

**Frontend:**

```
npm install @azure/msal-browser   (or load from CDN — no bundler needed)
```

- On page load: attempt silent token acquisition
- On failure: redirect to Entra login
- Access token attached to every API request as `Authorization: Bearer <token>`
- Org switcher in the header if the user belongs to multiple orgs
- UI elements (Add Resource, Edit, Delete buttons) hidden or disabled based on role returned in session info endpoint

**Environment variables added:**
```
ENTRA_TENANT_ID
ENTRA_CLIENT_ID
ENTRA_CLIENT_SECRET   # only needed if using client credentials for server-side calls
```

**Testing:** Mock Entra tokens in pytest using `pytest-asyncio` + token fixtures. Test that routes reject invalid/expired tokens and enforce org isolation.

---

### Phase 3 — Admin Panel

New section in the UI: `Admin` tab (visible only to org admins — tab hidden for member/read_only roles).

**Member management:**
- Invite by email (sends a Slack DM or email with a join link — TBD, see Open Questions)
- Assign/change roles (admin / member / read_only)
- Remove members

**Team management:**
- Create / rename / delete teams
- Add / remove members from teams

**Audit log viewer:**
- Filterable by user, resource, action type, date range
- Paginated (server-side)
- CSV export endpoint

**Org settings:**
- Display name / slug
- Entra group ID mapping (optional — auto-add users from a group)
- Org-level fallback Slack webhook (used if a resource has no webhook configured)
- `allow_member_delete` toggle (restrict deletion to admins only)

**Notification settings** (stored in `org_notification_settings`):
- Reminder cadence: configurable day offsets (default: 30, 14, 7, 3)
- Notification time: time-of-day picker (default: 09:00)
- Timezone: dropdown (drives both notification delivery time and display)
- Digest mode toggle: per-resource Slack messages vs. single daily digest per org

**Reports** (`GET /api/reports/upcoming` and `GET /api/reports/recent-changes`):
- Upcoming expiry report: all resources expiring within a configurable window (default 30 days), sorted by date
- Recent changes report: audit log entries from the last N days
- Both available as CSV download directly from the Admin panel UI
- No scheduled/email delivery in this phase — download on demand only

**Testing:** Full CRUD tests for each admin endpoint. Role enforcement tests (member/read_only cannot access admin routes).

---

### Phase 4 — DigitalOcean Deployment

**CI/CD (current implementation):**
1. Run pytest (fail fast on any test failure) — wired into `ci.yml` and `release.yml`
2. Build Docker image, push `latest` + semver tag to DO Container Registry
3. App Platform auto-redeploys via `deploy_on_push: true` on the `latest` tag
4. Manual `terraform apply` available via `deploy-dev.yml` (workflow_dispatch) for infrastructure changes
5. Alembic `upgrade head` run as a pre-deploy job once MySQL is active

**App Platform Terraform config:**
```yaml
name: tribal
services:
  - name: api
    image:
      registry_type: DOCR
      repository: tribal
      tag: latest
    instance_count: 2              # HA — two instances behind DO load balancer
    instance_size_slug: apps-s-1vcpu-0.5gb
    health_check:
      http_path: /healthz
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
      - key: REDIS_URL
        scope: RUN_TIME
        type: SECRET
      - key: ENTRA_TENANT_ID
        scope: RUN_TIME
        type: SECRET
      - key: ENTRA_CLIENT_ID
        scope: RUN_TIME
        type: SECRET
```

**TLS:** Handled automatically by DO App Platform on the custom domain.

**Logging:** App outputs JSON to stdout; DO App Platform ships logs to its log drain.

---

### Phase 5 — Unit & Integration Test Suite

Target: >80% coverage on all backend modules.

**Current state:** `tests/test_api.py` covers all resource CRUD, cert upload, webhook test, and healthz (20 tests, all passing). Wired into CI.

**Remaining:**
```
tests/
  conftest.py          # pytest fixtures: test DB, auth token mocks, test client
  test_resources.py    # rename from test_api.py; expand with org isolation tests
  test_scheduler.py    # reminder logic, deletion notifications
  test_auth.py         # token validation, org isolation, role enforcement
  test_admin.py        # member/team management, audit logs, notification settings
  test_migrations.py   # Alembic up/down for each migration
  test_reports.py      # upcoming + recent-changes CSV output
```

**Key fixtures:**
- `test_db` — spins up an in-memory SQLite (for unit tests) or a DO-provided test MySQL (for integration)
- `auth_headers(role)` — returns headers with a mock Entra JWT for the given role
- `org_with_members` — factory fixture creating an org with admin + member + read_only users

**Test types:**
- **Unit:** Business logic in isolation (scheduler reminders, cert parsing, date math)
- **Integration:** Full request→response via `httpx.AsyncClient` against a real test DB
- **Auth:** Every protected endpoint tested with no token, wrong-org token, insufficient role

---

### Phase 6 — Async Notifications (DB-backed queue)

**Motivation:** APScheduler running in-process has two problems at scale:
1. In a multi-instance HA deployment it will send duplicate reminders unless carefully locked
2. Notification delivery (Slack HTTP calls) blocks the scheduler thread

**Approach — DB as the queue (no new infrastructure):**

Use the existing MySQL/SQLite database as a simple task queue via a `notification_tasks` table. APScheduler becomes a lightweight dispatcher that writes rows; a separate polling loop processes them. No Redis, no Celery, no new services. Swap to Celery + Redis later by replacing only the enqueue/dequeue layer.

```
notification_tasks
  id            BIGINT PK AUTO_INCREMENT
  org_id        BIGINT FK → organizations.id NULL
  resource_id   BIGINT FK → resources.id NULL
  task_type     ENUM('reminder', 'deletion', 'digest') NOT NULL
  payload       JSON NOT NULL                     -- task-specific data
  status        ENUM('pending', 'processing', 'done', 'failed') NOT NULL DEFAULT 'pending'
  scheduled_at  DATETIME NOT NULL DEFAULT NOW()   -- not before this time
  attempts      INT NOT NULL DEFAULT 0
  last_error    TEXT NULL
  created_at    DATETIME NOT NULL DEFAULT NOW()
  processed_at  DATETIME NULL
  INDEX (status, scheduled_at)
```

**Scheduler flow:**
```
APScheduler cron (runs on one instance — DB lock or DO Functions)
  └─ evaluates due reminders, inserts rows into notification_tasks

APScheduler interval job (every 30s, same or separate process)
  └─ SELECT ... WHERE status='pending' AND scheduled_at <= NOW() LIMIT 10
  └─ UPDATE status='processing' (atomic, prevents double-processing)
  └─ execute Slack HTTP call
  └─ UPDATE status='done' (or 'failed' + increment attempts)
  └─ retry failed tasks up to 3 attempts with exponential backoff
```

**Deletion notifications:** When a resource is soft-deleted, a `notification_tasks` row is inserted immediately with `scheduled_at = NOW()` — picked up within the next 30s poll cycle.

**Hard-purge job:** A separate APScheduler cron checks for resources where `deleted_at <= NOW() - purge_after_days` and hard-deletes them (removes the row permanently).

**Task types:**
- `reminder` — per-resource Slack message at configured day thresholds
- `deletion` — notifies team when a resource is soft-deleted
- `digest` — daily summary for orgs with digest mode enabled

**Future migration path to Celery + Redis:**
Replace the DB poll loop with `task.delay()` calls; keep the same task function signatures. The `notification_tasks` table can be retired or kept as an audit trail.

**No new environment variables needed for Phase 6.**

---

## Open Questions / Decisions Needed

1. **Invite flow:** Email invite (requires SMTP setup) vs. Slack DM invite vs. just share a join link?
2. **Entra group mapping:** Should users be auto-added to an org based on their Entra group, or is manual invite the only path?
3. **Resource visibility:** Should all org members see all resources, or only team members see their team's resources? (Current assumption: org-wide visibility, teams are for notification grouping only.)
4. **Billing:** Is this a free internal tool for one org, or a paid multi-org SaaS? If paid, Stripe integration is a separate phase.
5. **MySQL standby:** Start with single node + daily DO backups, or pay the extra $15/mo for a standby node from day one?

**Resolved:**
- ~~Soft delete visibility~~ → Admins can view and restore soft-deleted resources within `purge_after_days`. A scheduled hard-purge job removes them permanently after that window. Recovery of mistakenly deleted resources is the primary driver.
- ~~Task broker~~ → DB-backed `notification_tasks` table; no Redis or Celery until scale demands it. Future migration path is well-defined (see Phase 6).
- ~~Notification config scope~~ → Org-level admin settings only. No per-resource overrides in this phase.
- ~~Reports delivery~~ → CSV download from the Admin panel UI on demand. No scheduled or email delivery for now.

---

## Notes for Implementation

- Each phase should be a separate branch / PR so changes are reviewable in isolation.
- Alembic migrations are one-way (no destructive rollbacks in production) — design schemas carefully before migrating.
- The `fastapi-azure-auth` library handles token validation and JWKS caching; do not re-implement JWT validation manually.
- MySQL 8 JSON column type is used for `audit_logs.detail` and `org_notification_settings.reminder_days` — SQLAlchemy's `JSON` type maps correctly.
- DigitalOcean Managed MySQL enforces SSL on connections by default — ensure `DATABASE_URL` includes `ssl_ca` or use `?ssl=true`.
- **Scheduler HA:** APScheduler must only run on one app instance. Until Celery is in place, use a DB-backed job store (SQLAlchemy store) with a distributed lock, or a DO Functions cron hitting an internal `/internal/run-reminders` endpoint protected by a shared secret. Once Celery is live, APScheduler becomes a thin dispatcher and HA is handled by the broker.
- **Soft deletes:** The `WHERE deleted_at IS NULL` filter must be applied as a SQLAlchemy query default (via a `__table_args__` expression or a shared dependency function) — not sprinkled manually across every route — to prevent accidental exposure.
- **Role enforcement:** The `read_only` role must be enforced on the frontend (hide Add/Edit/Delete UI) and the backend (HTTP 403 from the dependency). Never rely on UI-only enforcement.
