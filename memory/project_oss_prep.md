---
name: Tribal OSS prep & current stack
description: Current tech stack, repo cleanup done for open-source, and where roadmap/specs live
type: project
---

Tribal is a credential lifecycle management tool (TLS certs, API keys, SSH keys). Stack: Python 3.14 / FastAPI / SQLAlchemy / APScheduler, MySQL 8, Vue 3 + TypeScript + Vite + Tailwind, Docker, DigitalOcean App Platform, Terraform.

**OSS prep completed 2026-03-29:**
- Removed SAAS_ROADMAP.md, SECURITY_FINDINGS.md, TERRAFORM_PROVIDER_PLAN.md, docs/jira-integration.md
- Removed all 23 "Iteration" sections from README
- Added Mermaid architecture diagrams and a Roadmap section to README

**Why:** Preparing for open-source release. Implementation specs will be written outside the codebase going forward.

**How to apply:** Do not recreate plan/spec/roadmap .md files in the repo root. If asked to plan a feature, use the Plan tool or discuss inline — don't persist specs as repo files.

**Key files:**
- `app/main.py` — FastAPI app, middleware, lifespan (scheduler)
- `app/models.py` — SQLAlchemy models
- `app/schemas.py` — Pydantic schemas
- `app/routers/` — auth, resources, keys, admin
- `app/scheduler.py` — APScheduler notification jobs
- `app/providers/` — Slack, AWS, Azure, GitHub, etc.
- `frontend/src/` — Vue 3 SPA (views, components, stores, router)
- `alembic/` — DB migrations
- `terraform/` — DO App Platform infra
- `.github/workflows/release.yml` — CI: pytest → Docker → DOCR → App Platform redeploy
