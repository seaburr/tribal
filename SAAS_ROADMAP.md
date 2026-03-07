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
| **Total** | | **~$40/mo** |

If the standby node pushes over budget, defer it to phase 2 and rely on DO's daily automated backups for recovery initially.

---

## Implementation Phases

### Phase 0 — Foundation (pre-SaaS cleanup)

Before adding multi-tenancy, stabilize the existing codebase:

- [ ] Replace `ALTER TABLE` migration shim with proper Alembic setup
- [ ] Add `pytest` + `httpx` test suite for all existing API routes
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
  id            BIGINT PK AUTO_INCREMENT
  name          VARCHAR(255) NOT NULL
  slug          VARCHAR(64) UNIQUE NOT NULL   -- URL-friendly identifier
  entra_tenant_id  VARCHAR(128) UNIQUE        -- null until Entra is linked
  created_at    DATETIME NOT NULL DEFAULT NOW()

users
  id            BIGINT PK AUTO_INCREMENT
  entra_oid     VARCHAR(128) UNIQUE NOT NULL   -- Azure object ID
  email         VARCHAR(255) NOT NULL
  display_name  VARCHAR(255)
  created_at    DATETIME NOT NULL DEFAULT NOW()

org_memberships
  org_id        BIGINT FK → organizations.id
  user_id       BIGINT FK → users.id
  role          ENUM('admin', 'member') NOT NULL DEFAULT 'member'
  joined_at     DATETIME NOT NULL DEFAULT NOW()
  PRIMARY KEY (org_id, user_id)

teams
  id            BIGINT PK AUTO_INCREMENT
  org_id        BIGINT FK → organizations.id NOT NULL
  name          VARCHAR(255) NOT NULL
  created_at    DATETIME NOT NULL DEFAULT NOW()

team_memberships
  team_id       BIGINT FK → teams.id
  user_id       BIGINT FK → users.id
  PRIMARY KEY (team_id, user_id)

resources   (add columns to existing table)
  + org_id          BIGINT FK → organizations.id NOT NULL
  + team_id         BIGINT FK → teams.id NULL
  + created_by      BIGINT FK → users.id NULL

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

**All existing API queries** gain a mandatory `WHERE org_id = :current_org` filter applied by a FastAPI dependency — no cross-org leakage possible by construction.

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
       └─ require_role("admin") → OrgMembership (raises 403 if insufficient)
```

Every protected route declares which dependency it needs. This keeps auth logic out of business logic.

**Frontend:**

```
npm install @azure/msal-browser   (or load from CDN — no bundler needed)
```

- On page load: attempt silent token acquisition
- On failure: redirect to Entra login
- Access token attached to every API request as `Authorization: Bearer <token>`
- Org switcher in the header if the user belongs to multiple orgs

**Environment variables added:**
```
ENTRA_TENANT_ID
ENTRA_CLIENT_ID
ENTRA_CLIENT_SECRET   # only needed if using client credentials for server-side calls
```

**Testing:** Mock Entra tokens in pytest using `pytest-asyncio` + token fixtures. Test that routes reject invalid/expired tokens and enforce org isolation.

---

### Phase 3 — Admin Panel

New section in the UI: `/admin` (visible only to org admins).

**Member management:**
- Invite by email (sends a Slack DM or email with a join link — TBD)
- Assign/change roles
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
- Notification preferences: enable/disable reminder cadences org-wide, or override to digest mode

**Digest mode:** Instead of per-resource Slack messages, send one daily digest per org summarizing all upcoming expirations. Toggle per org in settings.

**Testing:** Full CRUD tests for each admin endpoint. Role enforcement tests (member cannot access admin routes).

---

### Phase 4 — DigitalOcean Deployment

**App Platform configuration (`app.yaml`):**
```yaml
name: tribal
services:
  - name: api
    image:
      registry_type: DOCR          # DigitalOcean Container Registry
      repository: tribal
      tag: latest
    instance_count: 2              # HA — two instances behind DO load balancer
    instance_size_slug: basic-xs   # 512MB RAM, 0.5 vCPU — $5/instance/mo
    health_check:
      http_path: /healthz
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        type: SECRET
      - key: ENTRA_TENANT_ID
        scope: RUN_TIME
        type: SECRET
      - key: ENTRA_CLIENT_ID
        scope: RUN_TIME
        type: SECRET
databases:
  - name: tribal-db
    engine: MYSQL
    version: "8"
    size: db-s-1vcpu-1gb           # $15/mo
    num_nodes: 1                   # upgrade to 2 for standby when budget allows
```

**CI/CD:** GitHub Actions workflow:
1. Run pytest (fail fast on any test failure)
2. Build Docker image, push to DO Container Registry
3. Trigger App Platform deploy via DO API
4. Run Alembic `upgrade head` as a pre-deploy job (App Platform run job)

**TLS:** Handled automatically by DO App Platform on the custom domain. No Nginx/Caddy config needed.

**Health check:** Add `GET /healthz` endpoint returning `{"status": "ok"}` — used by DO load balancer to route traffic only to healthy instances.

**Logging:** App outputs JSON to stdout; DO App Platform ships logs to its log drain. Add a log drain to Papertrail or DO's own monitoring if needed.

---

### Phase 5 — Unit & Integration Test Suite

Target: >80% coverage on all backend modules.

**Test structure:**
```
tests/
  conftest.py          # pytest fixtures: test DB, auth token mocks, test client
  test_resources.py    # CRUD, cert upload, webhook test
  test_scheduler.py    # reminder logic, deletion notifications
  test_auth.py         # token validation, org isolation, role enforcement
  test_admin.py        # member/team management, audit logs
  test_migrations.py   # Alembic up/down for each migration
```

**Key fixtures:**
- `test_db` — spins up an in-memory SQLite (for unit tests) or a DO-provided test MySQL (for integration)
- `auth_headers(role)` — returns headers with a mock Entra JWT for the given role
- `org_with_members` — factory fixture creating an org with admin + member users

**Test types:**
- **Unit:** Business logic in isolation (scheduler reminders, cert parsing, date math)
- **Integration:** Full request→response via `httpx.AsyncClient` against a real test DB
- **Auth:** Every protected endpoint tested with no token, wrong-org token, insufficient role

---

## Open Questions / Decisions Needed

1. **Invite flow:** Email invite (requires SMTP setup) vs. Slack DM invite vs. just share a join link?
2. **Entra group mapping:** Should users be auto-added to an org based on their Entra group, or is manual invite the only path?
3. **Resource visibility:** Should all org members see all resources, or only team members see their team's resources? (Current assumption: org-wide visibility, teams are for notification grouping only.)
4. **Billing:** Is this a free internal tool for one org, or a paid multi-org SaaS? If paid, Stripe integration is a separate phase.
5. **MySQL standby:** Start with single node + daily DO backups, or pay the extra $15/mo for a standby node from day one?

---

## Notes for Implementation

- Each phase should be a separate branch / PR so changes are reviewable in isolation.
- Alembic migrations are one-way (no destructive rollbacks in production) — design schemas carefully before migrating.
- The `fastapi-azure-auth` library handles token validation and JWKS caching; do not re-implement JWT validation manually.
- MySQL 8 JSON column type is used for `audit_logs.detail` — SQLAlchemy's `JSON` type maps correctly.
- DigitalOcean Managed MySQL enforces SSL on connections by default — ensure `DATABASE_URL` includes `ssl_ca` or use `?ssl=true`.
- The scheduler (APScheduler) must only run on **one** app instance in the HA setup to avoid duplicate reminders. Use a DB-backed job store (SQLAlchemy store for APScheduler) with a lock, or move scheduled jobs to a DO Functions (serverless cron) that hits an internal `/internal/run-reminders` endpoint protected by a shared secret.
