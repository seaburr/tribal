import csv
import io
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..audit import write_audit
from ..database import get_db
from ..dependencies import get_current_user, require_admin
from ..scheduler import _TRIBAL_FOOTER

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# ── Settings ──────────────────────────────────────────────────────────────────

def _get_or_create_settings(db: Session) -> models.AdminSettings:
    settings = db.get(models.AdminSettings, 1)
    if not settings:
        settings = models.AdminSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.post("/webhook-test", status_code=204)
async def test_admin_webhook(req: schemas.WebhookTestRequest):
    payload = {
        "text": "This is a test message from Tribal for the admin Slack webhook.",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": ":white_check_mark: Admin Webhook Test"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Your admin webhook is configured correctly. Tribal will send admin-level notifications to this channel."},
            },
            _TRIBAL_FOOTER,
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(req.webhook_url, json=payload, timeout=10)
            if r.status_code >= 400:
                raise HTTPException(status_code=400, detail=f"Webhook returned HTTP {r.status_code}. Check the URL and try again.")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Could not reach webhook: {e}")


@router.get("/settings", response_model=schemas.AdminSettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return _get_or_create_settings(db)


@router.put("/settings", response_model=schemas.AdminSettingsResponse)
def update_settings(updates: schemas.AdminSettingsUpdate, db: Session = Depends(get_db)):
    if not updates.reminder_days:
        raise HTTPException(status_code=422, detail="At least one reminder day is required.")
    if any(d <= 0 or d > 365 for d in updates.reminder_days):
        raise HTTPException(status_code=422, detail="Reminder days must be between 1 and 365.")
    if not (0 <= updates.notify_hour <= 23):
        raise HTTPException(status_code=422, detail="Notify hour must be between 0 and 23.")

    settings = _get_or_create_settings(db)
    settings.org_name = updates.org_name.strip() if updates.org_name and updates.org_name.strip() else None
    settings.reminder_days = sorted(set(updates.reminder_days), reverse=True)
    settings.notify_hour = updates.notify_hour
    settings.slack_webhook = updates.slack_webhook or None
    settings.alert_on_overdue = updates.alert_on_overdue
    settings.alert_on_delete = updates.alert_on_delete
    settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings)
    return settings


# ── Team (singleton) ───────────────────────────────────────────────────────────

@router.get("/teams", response_model=list[schemas.TeamResponse])
def list_teams(db: Session = Depends(get_db)):
    """Returns 0 or 1 team — there is only ever one team in the system."""
    return db.query(models.Team).all()


@router.post("/teams", response_model=schemas.TeamResponse, status_code=201)
def create_team(
    req: schemas.TeamCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create the singleton team. Returns 409 if one already exists."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Team name cannot be empty.")
    if db.query(models.Team).first():
        raise HTTPException(status_code=409, detail="A team already exists. Use PUT /admin/teams/{id} to rename it.")
    team = models.Team(name=name)
    db.add(team)
    db.commit()
    db.refresh(team)
    write_audit(db, "team.create", user_email=current_user.email, detail={"team_name": name})
    return team


@router.put("/teams/{team_id}", response_model=schemas.TeamResponse)
def rename_team(
    team_id: int,
    req: schemas.TeamCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Rename the singleton team."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Team name cannot be empty.")
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    old_name = team.name
    team.name = name
    db.commit()
    db.refresh(team)
    write_audit(db, "team.rename", user_email=current_user.email, detail={"old_name": old_name, "new_name": name})
    return team


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.created_at).all()


@router.put("/users/{user_id}/role", response_model=schemas.UserResponse)
def set_user_admin(
    user_id: int,
    is_admin: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Account creator's admin rights are permanent
    if target.is_account_creator and not is_admin:
        raise HTTPException(status_code=400, detail="Cannot revoke admin rights from the account creator.")

    # Prevent demoting the last admin
    if target.is_admin and not is_admin:
        admin_count = db.query(models.User).filter(models.User.is_admin == True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin.")

    if target.is_admin != is_admin:
        action_label = "granted" if is_admin else "revoked"
        write_audit(
            db,
            "user.role_change",
            user_email=current_user.email,
            detail={
                "target_user": target.email,
                "action": action_label,
                "new_role": "admin" if is_admin else "member",
            },
        )

    target.is_admin = is_admin
    db.commit()
    db.refresh(target)
    return target


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.is_account_creator:
        raise HTTPException(status_code=400, detail="Cannot delete the account creator.")
    write_audit(db, "user.delete", user_email=current_user.email, detail={"deleted_user": target.email})
    db.delete(target)
    db.commit()


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/resources/deleted", response_model=list[schemas.DeletedResourceResponse])
def list_deleted_resources(db: Session = Depends(get_db)):
    return (
        db.query(models.Resource)
        .filter(models.Resource.deleted_at.isnot(None))
        .order_by(models.Resource.deleted_at.desc())
        .all()
    )


@router.post("/resources/{resource_id}/restore", response_model=schemas.ResourceResponse)
def restore_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = (
        db.query(models.Resource)
        .filter(models.Resource.id == resource_id, models.Resource.deleted_at.isnot(None))
        .first()
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Deleted resource not found.")
    resource.deleted_at = None
    resource.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("/audit-log", response_model=list[schemas.AuditLogEntry])
def get_audit_log(
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    limit = min(limit, 500)
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ── API Keys (admin view) ──────────────────────────────────────────────────────

@router.get("/api-keys", response_model=list[schemas.ApiKeyAdminResponse])
def list_all_api_keys(db: Session = Depends(get_db)):
    keys = (
        db.query(models.ApiKey, models.User.email)
        .join(models.User, models.ApiKey.user_id == models.User.id)
        .filter(models.ApiKey.revoked_at.is_(None))
        .order_by(models.ApiKey.created_at.desc())
        .all()
    )
    results = []
    for key, email in keys:
        results.append(schemas.ApiKeyAdminResponse(
            id=key.id,
            name=key.name,
            key_prefix=key.key_prefix,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            revoked_at=key.revoked_at,
            user_email=email,
        ))
    return results


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_any_api_key(key_id: int, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    api_key = db.get(models.ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found.")
    if api_key.revoked_at:
        raise HTTPException(status_code=400, detail="Key is already revoked.")
    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports/upcoming")
def report_upcoming(db: Session = Depends(get_db)):
    today = date.today()
    cutoff = today + timedelta(days=30)
    resources = (
        db.query(models.Resource)
        .filter(models.Resource.expiration_date <= cutoff)
        .order_by(models.Resource.expiration_date)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Type", "DRI", "Expiration Date", "Days Until Expiration", "Purpose", "Secret Manager Link"])
    for r in resources:
        days = (r.expiration_date - today).days
        writer.writerow([
            r.name,
            r.type,
            r.dri,
            r.expiration_date.strftime("%m/%d/%Y"),
            days,
            r.purpose,
            r.secret_manager_link or "",
        ])

    output.seek(0)
    filename = f"tribal-upcoming-{today.isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/recent-changes")
def report_recent_changes(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    entries = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.created_at >= since)
        .order_by(models.AuditLog.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date/Time (UTC)", "User", "Action", "Resource", "Detail"])
    for e in entries:
        writer.writerow([
            e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            e.user_email or "system",
            e.action,
            e.resource_name or "",
            str(e.detail) if e.detail else "",
        ])

    output.seek(0)
    filename = f"tribal-changes-{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
