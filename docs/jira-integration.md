# JIRA Integration — Implementation Spec

## Overview

This document covers the effort and code changes required to add JIRA as a notification channel alongside (or instead of) Slack. When enabled, Tribal would create a JIRA issue on the configured project each time a resource triggers a reminder (30, 14, 7, 3, 1 days before expiry and/or on overdue).

---

## Scope

| In scope | Out of scope |
|---|---|
| Creating JIRA issues from the reminder scheduler | Two-way sync (resolving issues when resource is updated) |
| Admin UI to configure the JIRA connection | JIRA OAuth — Basic Auth (email + API token) only |
| "Send Test" button for the JIRA connection | Per-resource JIRA project overrides |
| Channel selector: Slack / JIRA / Both | JIRA Service Management (JSM) request types |
| De-duplication (one issue per reminder interval per resource) | Assignee lookup via JIRA account ID |

---

## Required Changes

### 1. Database — New migration

**File:** `alembic/versions/0006_jira_settings.py`

Add columns to the `admin_settings` table:

```python
# nullable=True columns need no server_default — existing rows get NULL
op.add_column("admin_settings", sa.Column("jira_base_url",    sa.String(512), nullable=True))
op.add_column("admin_settings", sa.Column("jira_project_key", sa.String(32),  nullable=True))
op.add_column("admin_settings", sa.Column("jira_api_token",   sa.String(512), nullable=True))
op.add_column("admin_settings", sa.Column("jira_user_email",  sa.String(255), nullable=True))

# nullable=True with a string default: use sa.text() with embedded SQL quotes so MySQL
# renders DEFAULT 'Task' (string literal) rather than DEFAULT Task (invalid identifier).
op.add_column("admin_settings", sa.Column("jira_issue_type",
    sa.String(64), nullable=True, server_default=sa.text("'Task'")))

# NOT NULL with a string default requires the same pattern.
op.add_column("admin_settings", sa.Column("notification_channel",
    sa.String(16), nullable=False, server_default=sa.text("'slack'")))
```

> **MySQL rule for string `server_default`:** pass `sa.text("'value'")` — the outer Python string is
> the raw SQL fragment, and the inner single-quotes make it a SQL string literal.
> `server_default="slack"` (bare string) renders as `DEFAULT slack`, which MySQL interprets as a
> column name and raises a syntax error.
> For boolean columns use `sa.false()` / `sa.true()` (dialect-aware) instead of `server_default="0"`,
> which SQLAlchemy may render as `DEFAULT '0'` (quoted) and MySQL strict mode can reject.

Add a new `jira_issue_log` table to prevent duplicate issue creation:

```python
op.create_table(
    "jira_issue_log",
    sa.Column("id",           sa.Integer(),  nullable=False),
    sa.Column("resource_id",  sa.Integer(),  nullable=False),
    sa.Column("reminder_days", sa.Integer(), nullable=False),
    sa.Column("issue_key",    sa.String(32), nullable=False),
    sa.Column("created_at",   sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
)
op.create_index(op.f("ix_jira_issue_log_resource_id"), "jira_issue_log", ["resource_id"])
```

> **MySQL rule for `op.create_table`:** define `ForeignKeyConstraint` and `PrimaryKeyConstraint`
> as named table-level constraints (matching the pattern in migration 0001) rather than inline
> `sa.ForeignKey()` inside the column definition. Inline FK syntax in `op.create_table` is
> unreliable across dialects.


**Model additions (`app/models.py`):**

```python
class AdminSettings(Base):
    # ... existing fields ...
    jira_base_url         = Column(String(512), nullable=True)
    jira_project_key      = Column(String(32),  nullable=True)
    jira_api_token        = Column(String(512), nullable=True)
    jira_user_email       = Column(String(255), nullable=True)
    jira_issue_type       = Column(String(64),  nullable=True, default="Task")
    notification_channel  = Column(String(16),  nullable=False, default="slack")

class JiraIssueLog(Base):
    __tablename__ = "jira_issue_log"
    id            = Column(Integer, primary_key=True)
    resource_id   = Column(Integer, ForeignKey("resources.id"), nullable=False)
    reminder_days = Column(Integer, nullable=False)
    issue_key     = Column(String(32), nullable=False)
    created_at    = Column(DateTime, default=_utcnow)
```

---

### 2. JIRA Client — New file

**File:** `app/jira_client.py`

Thin async wrapper around the JIRA REST API v3. Uses `httpx.AsyncClient` (already a transitive dependency via FastAPI).

```python
import httpx
import logging
from typing import Optional

log = logging.getLogger(__name__)

JIRA_API_VERSION = "rest/api/3"


async def create_issue(
    base_url: str,
    user_email: str,
    api_token: str,
    project_key: str,
    issue_type: str,
    summary: str,
    description_adf: dict,  # Atlassian Document Format
    due_date: Optional[str] = None,  # ISO date string
) -> dict:
    """
    Creates a JIRA issue and returns the response JSON (contains 'key', 'id', 'self').
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    url = f"{base_url.rstrip('/')}/{JIRA_API_VERSION}/issue"
    payload = {
        "fields": {
            "project":   {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary":   summary,
            "description": description_adf,
        }
    }
    if due_date:
        payload["fields"]["duedate"] = due_date

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json=payload,
            auth=(user_email, api_token),
        )
        resp.raise_for_status()
        return resp.json()


def build_description_adf(resource) -> dict:
    """
    Converts resource fields into Atlassian Document Format (ADF) for rich-text
    JIRA issue descriptions.
    """
    def paragraph(text: str) -> dict:
        return {
            "type": "paragraph",
            "content": [{"type": "text", "text": text}]
        }

    def heading(text: str, level: int = 3) -> dict:
        return {
            "type": "heading",
            "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]
        }

    return {
        "version": 1,
        "type": "doc",
        "content": [
            heading("Resource Details"),
            paragraph(f"DRI: {resource.dri}"),
            paragraph(f"Expiration: {resource.expiration_date}"),
            paragraph(f"Type: {resource.type}"),
            heading("Purpose / Usage"),
            paragraph(resource.purpose or "—"),
            heading("Generation / Rotation Instructions"),
            paragraph(resource.generation_instructions or "—"),
            *(
                [paragraph(f"Secret Manager: {resource.secret_manager_link}")]
                if resource.secret_manager_link else []
            ),
            paragraph("This issue was created automatically by Tribal."),
        ]
    }
```

**Note on API token security:** The `jira_api_token` value is stored in the database. For production, consider encrypting it at rest using the same approach used for the JWT secret (environment-variable-based key). At minimum, the token should never be returned to the frontend in any API response.

---

### 3. Schemas — New fields

**File:** `app/schemas.py`

```python
class AdminSettingsResponse(BaseModel):
    # ... existing fields ...
    jira_base_url:        Optional[str] = None
    jira_project_key:     Optional[str] = None
    jira_user_email:      Optional[str] = None
    jira_issue_type:      Optional[str] = "Task"
    notification_channel: str = "slack"
    # jira_api_token intentionally omitted — write-only

class AdminSettingsUpdate(BaseModel):
    # ... existing fields ...
    jira_base_url:        Optional[str] = None
    jira_project_key:     Optional[str] = None
    jira_api_token:       Optional[str] = None  # write-only; empty string = clear token
    jira_user_email:      Optional[str] = None
    jira_issue_type:      Optional[str] = None
    notification_channel: Optional[str] = None  # "slack" | "jira" | "both"
```

---

### 4. Admin Router — New endpoints

**File:** `app/routers/admin.py`

```python
# Add to PUT /admin/settings:
if payload.notification_channel is not None:
    settings.notification_channel = payload.notification_channel
if payload.jira_base_url is not None:
    settings.jira_base_url = payload.jira_base_url
if payload.jira_project_key is not None:
    settings.jira_project_key = payload.jira_project_key
if payload.jira_api_token is not None:
    settings.jira_api_token = payload.jira_api_token or None  # empty string clears token
if payload.jira_user_email is not None:
    settings.jira_user_email = payload.jira_user_email
if payload.jira_issue_type is not None:
    settings.jira_issue_type = payload.jira_issue_type

# New endpoint:
@router.post("/jira/test")
async def test_jira_connection(db: Session = Depends(get_db), current_user = Depends(require_admin)):
    settings = _get_settings(db)
    if not all([settings.jira_base_url, settings.jira_user_email,
                settings.jira_api_token, settings.jira_project_key]):
        raise HTTPException(status_code=400, detail="JIRA connection is not fully configured.")
    try:
        result = await jira_client.create_issue(
            base_url=settings.jira_base_url,
            user_email=settings.jira_user_email,
            api_token=settings.jira_api_token,
            project_key=settings.jira_project_key,
            issue_type=settings.jira_issue_type or "Task",
            summary="[Tribal] Test issue — connection verified",
            description_adf=jira_client.build_description_adf_text(
                "This is a test issue created by Tribal to verify the JIRA connection."
            ),
        )
        return {"issue_key": result["key"], "issue_url": f"{settings.jira_base_url}/browse/{result['key']}"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"JIRA API error: {str(e)}")
```

---

### 5. Scheduler — De-duplicated JIRA issue creation

**File:** `app/scheduler.py`

The existing `check_reminders()` function iterates resources and fires Slack messages. The updated version would:

1. Read `settings.notification_channel`
2. For each resource/interval combination, check `JiraIssueLog` before creating an issue
3. Log the created issue key to prevent duplicates on the next scheduler run

```python
async def _maybe_create_jira_issue(db, settings, resource, days_until):
    from app import jira_client

    # Check if we already filed a JIRA issue for this resource + interval
    existing = db.query(models.JiraIssueLog).filter(
        models.JiraIssueLog.resource_id == resource.id,
        models.JiraIssueLog.reminder_days == days_until,
    ).first()
    if existing:
        return  # already filed

    summary = (
        f"[Tribal] {resource.name} expires in {days_until} day{'s' if days_until != 1 else ''}"
        if days_until > 0
        else f"[Tribal] {resource.name} is overdue"
    )
    description = jira_client.build_description_adf(resource)

    try:
        result = await jira_client.create_issue(
            base_url=settings.jira_base_url,
            user_email=settings.jira_user_email,
            api_token=settings.jira_api_token,
            project_key=settings.jira_project_key,
            issue_type=settings.jira_issue_type or "Task",
            summary=summary,
            description_adf=description,
            due_date=resource.expiration_date,
        )
        db.add(models.JiraIssueLog(
            resource_id=resource.id,
            reminder_days=days_until,
            issue_key=result["key"],
        ))
        db.commit()
        log.info("Created JIRA issue %s for resource %s", result["key"], resource.id)
    except Exception as e:
        log.error("Failed to create JIRA issue for resource %s: %s", resource.id, e)


# In check_reminders(), replace/augment the Slack call:
channel = settings.notification_channel or "slack"
if channel in ("slack", "both") and resource.slack_webhook:
    await send_slack_notification(...)
if channel in ("jira", "both") and all([settings.jira_base_url, settings.jira_api_token]):
    await _maybe_create_jira_issue(db, settings, resource, days_remaining)
```

**De-duplication note:** The `JiraIssueLog` records need to be cleared when a resource is updated (its expiry date changes), otherwise the next expiry cycle would be suppressed. Add a cleanup step in the resource update handler:

```python
# In resources router, on successful PUT:
db.query(models.JiraIssueLog).filter(
    models.JiraIssueLog.resource_id == resource_id
).delete()
```

---

### 6. Admin UI

**File:** `static/index.html` — Add a new section to Notification Settings:

```html
<div class="admin-form-row" id="jira-config-row">
  <div class="admin-form-group">
    <label>Notification Channel</label>
    <select id="adm-notification-channel">
      <option value="slack">Slack only</option>
      <option value="jira">JIRA only</option>
      <option value="both">Slack + JIRA</option>
    </select>
  </div>
</div>
<div class="admin-form-row" id="jira-fields-row" style="display:none">
  <div class="admin-form-group">
    <label for="adm-jira-url">JIRA Base URL</label>
    <input type="url" id="adm-jira-url" placeholder="https://yourorg.atlassian.net" />
  </div>
  <div class="admin-form-group">
    <label for="adm-jira-project">Project Key</label>
    <input type="text" id="adm-jira-project" placeholder="OPS" />
  </div>
  <div class="admin-form-group">
    <label for="adm-jira-email">JIRA User Email</label>
    <input type="email" id="adm-jira-email" placeholder="admin@yourorg.com" />
  </div>
  <div class="admin-form-group">
    <label for="adm-jira-token">API Token <span class="optional">(write-only)</span></label>
    <div class="webhook-row">
      <input type="password" id="adm-jira-token" placeholder="Enter new token to update…" />
      <button type="button" class="btn-test" onclick="testJiraConnection()">Test</button>
    </div>
    <div id="jira-test-status" class="webhook-test-status"></div>
    <span class="admin-field-hint">Generate at <strong>Atlassian Account → Security → API tokens</strong>. Token is stored server-side and never returned to the browser.</span>
  </div>
  <div class="admin-form-group">
    <label for="adm-jira-issue-type">Issue Type</label>
    <input type="text" id="adm-jira-issue-type" placeholder="Task" />
    <span class="admin-field-hint">Must match an issue type name in the target project (e.g. Task, Bug, Story).</span>
  </div>
</div>
```

Show/hide the JIRA fields based on the channel selector value. Include `testJiraConnection()` in `app.js` to call `POST /admin/jira/test` and display the created issue URL on success.

---

## Testing Plan

| Test | What to verify |
|---|---|
| `test_jira_create_issue` | Mock `httpx.AsyncClient.post`; assert correct URL, auth header, and ADF body |
| `test_jira_test_endpoint_missing_config` | `POST /admin/jira/test` returns 400 when fields are incomplete |
| `test_jira_test_endpoint_api_error` | Returns 502 when JIRA returns non-2xx |
| `test_jira_deduplication` | Second scheduler run for the same resource+interval does not call JIRA API again |
| `test_jira_log_cleared_on_resource_update` | Updating a resource's expiry date removes `JiraIssueLog` entries |
| `test_notification_channel_both` | Both Slack and JIRA calls are made when channel = "both" |
| `test_notification_channel_jira_only` | Slack is skipped when channel = "jira" |

Use `respx` (httpx mock library) or `unittest.mock.AsyncMock` to mock the JIRA API calls without hitting Atlassian.

---

## Effort Estimate

| Area | Estimate |
|---|---|
| Migration + model | 1–2 hours |
| `jira_client.py` + ADF builder | 2–3 hours |
| Scheduler integration + de-duplication | 2–3 hours |
| Admin router endpoints + schema | 1–2 hours |
| Admin UI (fields, toggle, test button) | 2–3 hours |
| Tests | 2–3 hours |
| **Total** | **~10–16 hours** |

---

## Open Questions

1. **Token encryption at rest** — Should `jira_api_token` be encrypted in the DB (e.g. Fernet/AES using a `ENCRYPTION_KEY` env var)? Low risk if the DB is not directly exposed, but worth discussing before shipping.
2. **Issue resolution** — Should Tribal add a comment or resolve the JIRA issue when the resource expiry date is updated? This would require storing the issue key per resource (not just per interval) and a JIRA transition call.
3. **Assignee mapping** — JIRA requires an `accountId` for assignee, not a plain email. Is a manual mapping table (DRI email → JIRA account ID) acceptable, or should we skip auto-assignment and leave the field blank?
4. **Overdue issues** — Should a separate JIRA issue be filed for overdue resources, or should the last reminder's issue be updated/transitioned?
