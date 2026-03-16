from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user, require_write_access
from ..cert_utils import extract_expiry_from_pem, fetch_cert_expiry_from_endpoint
from ..scheduler import send_deletion_notification, send_admin_deletion_notification, _TRIBAL_FOOTER

router = APIRouter(prefix="/api/resources", tags=["resources"])

BLOCKED_EXTENSIONS = {".key", ".p12", ".p7b", ".pfx"}
ALLOWED_EXTENSIONS = {".pem", ".crt", ".cer"}
PRIVATE_KEY_MARKERS = ["PRIVATE KEY", "RSA PRIVATE", "EC PRIVATE", "ENCRYPTED PRIVATE", "DSA PRIVATE"]


_TYPE_DISPLAY: dict[str, str] = {
    "api_key": "API Key",
    "certificate": "Certificate",
    "ssh_key": "SSH Key",
    "other": "Other",
}


def _friendly_type(t: str) -> str:
    """Return the display-friendly name for a resource type.

    Handles snake_case variants that may come from the Terraform provider or
    other API clients (e.g. ``"api_key"`` → ``"API Key"``).
    """
    return _TYPE_DISPLAY.get(t.lower().replace(" ", "_"), t)


def _active(db: Session):
    """Base query for non-deleted resources."""
    return db.query(models.Resource).filter(models.Resource.deleted_at.is_(None))


def _audit(db: Session, action: str, resource: models.Resource, user: Optional[models.User], detail: Optional[dict] = None, via: str = "ui"):
    try:
        db.add(models.AuditLog(
            user_email=user.email if user else None,
            resource_id=resource.id,
            resource_name=resource.name,
            action=action,
            detail={**(detail or {}), "via": via},
        ))
        db.commit()
    except Exception:
        pass  # audit logging must never break the main flow


@router.get("/teams", response_model=list[schemas.TeamResponse])
def list_teams(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return db.query(models.Team).order_by(models.Team.name).all()


@router.post("/cert-lookup", response_model=schemas.CertLookupResponse)
async def lookup_cert_expiry(
    req: schemas.CertLookupRequest,
    _: models.User = Depends(get_current_user),
):
    """Connect to a TLS endpoint and return its certificate's expiry date."""
    import socket
    import ssl

    try:
        expiry = fetch_cert_expiry_from_endpoint(req.endpoint)
        return {"expiration_date": expiry}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except socket.timeout:
        raise HTTPException(status_code=400, detail="Connection timed out. Check the hostname and port.")
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {e}")
    except ConnectionRefusedError:
        raise HTTPException(status_code=400, detail="Connection refused. Is TLS running on that port?")
    except ssl.SSLError as e:
        raise HTTPException(status_code=400, detail=f"TLS error: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not retrieve certificate: {e}")


@router.post("/webhook-test", status_code=204)
async def test_webhook(
    req: schemas.WebhookTestRequest,
    _: models.User = Depends(get_current_user),
):
    payload = {
        "text": "This is a test message from Tribal.",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": ":white_check_mark: Tribal webhook test"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Your webhook is configured correctly. Tribal will send reminders to this channel."},
            },
            _TRIBAL_FOOTER,
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(req.webhook_url, json=payload, timeout=10)
            if r.status_code >= 400:
                raise HTTPException(status_code=400, detail=f"Webhook returned HTTP {r.status_code}. Check the URL and try again.")
    except (httpx.RequestError, httpx.InvalidURL) as e:
        raise HTTPException(status_code=400, detail=f"Could not reach webhook: {e}")


@router.get("/", response_model=list[schemas.ResourceResponse])
def list_resources(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return _active(db).order_by(models.Resource.expiration_date).all()


@router.post("/", response_model=schemas.ResourceResponse, status_code=201)
def create_resource(
    request: Request,
    resource: schemas.ResourceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_write_access),
):
    data = resource.model_dump()
    # Auto-assign the singleton team if one exists and none was specified
    if not data.get("team_id"):
        team = db.query(models.Team).first()
        if team:
            data["team_id"] = team.id
    db_resource = models.Resource(**data)
    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)
    _audit(db, "resource.create", db_resource, current_user, {"type": _friendly_type(db_resource.type)}, via=getattr(request.state, "auth_via", "ui"))
    return db_resource


@router.get("/{resource_id}", response_model=schemas.ResourceResponse)
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.put("/{resource_id}", response_model=schemas.ResourceResponse)
def update_resource(
    request: Request,
    resource_id: int,
    updates: schemas.ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_write_access),
):
    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    update_data = updates.model_dump(exclude_unset=True)
    # Only record fields whose values actually changed
    changed_fields = [
        field for field, new_val in update_data.items()
        if str(getattr(resource, field, None)) != str(new_val)
    ]
    for field, value in update_data.items():
        setattr(resource, field, value)

    resource.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resource)
    _audit(db, "resource.update", resource, current_user, {"updated_fields": changed_fields}, via=getattr(request.state, "auth_via", "ui"))
    return resource


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    request: Request,
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_write_access),
):
    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    _audit(db, "resource.delete", resource, current_user, {"type": _friendly_type(resource.type), "dri": resource.dri}, via=getattr(request.state, "auth_via", "ui"))
    deleted_by = current_user.display_name or current_user.email if current_user else None
    await send_deletion_notification(resource, deleted_by=deleted_by)
    # Notify admin webhook if alert_on_delete is enabled
    admin_settings = db.get(models.AdminSettings, 1)
    if admin_settings and admin_settings.alert_on_delete and admin_settings.slack_webhook:
        await send_admin_deletion_notification(resource, admin_settings.slack_webhook, deleted_by=deleted_by)
    resource.deleted_at = datetime.now(timezone.utc)
    db.commit()


_REPORT_ACTION_LABELS: dict[str, str] = {
    "resource.create": "Created",
    "resource.update": "Updated",
    "resource.delete": "Deleted",
    "resource.cert_upload": "Certificate Uploaded",
}


@router.get("/{resource_id}/report")
def get_resource_report(
    resource_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Generate and return a PDF overview report for a resource.

    Accessible by all authenticated users regardless of role.
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    from datetime import date as date_type

    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    audit_entries = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.resource_id == resource_id)
        .order_by(models.AuditLog.created_at)
        .all()
    )

    # Determine creator from the first resource.create audit entry
    create_entry = next((e for e in audit_entries if e.action == "resource.create"), None)
    creator = create_entry.user_email if create_entry else None

    today = date_type.today()
    delta = (resource.expiration_date - today).days
    if delta < 0:
        status_str = f"{abs(delta)} day(s) overdue"
    elif delta == 0:
        status_str = "Expires today"
    else:
        status_str = f"{delta} day(s) remaining"

    def _s(text) -> str:
        """Convert to a latin-1-safe string for the PDF core font."""
        if text is None:
            return "-"
        return str(text).encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # ── Title ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 9, _s(resource.name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(
        0, 5,
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    # ── Resource Details ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Resource Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    def _field(label: str, value) -> None:
        if not value and value != 0:
            return
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, _s(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _s(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)

    _field("Type", resource.type)
    _field("DRI", resource.dri)
    _field(
        "Expiration / Rotation Date",
        f"{resource.expiration_date.isoformat()} ({status_str})",
    )
    _field("Purpose / Usage", resource.purpose)
    _field("Generation / Rotation Instructions", resource.generation_instructions)
    if resource.secret_manager_link:
        _field("Secret Manager Link", resource.secret_manager_link)
    if resource.certificate_url:
        _field("Certificate URL", resource.certificate_url)
    if resource.auto_refresh_expiry:
        _field("Auto-refresh Expiry", "Enabled")

    created_label = (
        f"{resource.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
        + (f"  by {creator}" if creator else "")
    )
    _field("Created", created_label)
    _field("Last Updated", resource.updated_at.strftime("%Y-%m-%d %H:%M UTC"))

    pdf.ln(3)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(5)

    # ── Change History ────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Change History", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    if not audit_entries:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 5, "No audit entries recorded.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
    else:
        # Header row
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 235, 235)
        w_date, w_user, w_action, w_detail = 42, 52, 34, 52
        pdf.cell(w_date,   6, "Date / Time (UTC)", border=1, fill=True)
        pdf.cell(w_user,   6, "User",              border=1, fill=True)
        pdf.cell(w_action, 6, "Action",            border=1, fill=True)
        pdf.cell(w_detail, 6, "Detail",            border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 8)
        for entry in audit_entries:
            dt_str = entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "—"
            user_str = _s(entry.user_email or "system")[:28]
            action_str = _s(_REPORT_ACTION_LABELS.get(entry.action, entry.action))
            detail = entry.detail or {}
            parts: list[str] = []
            if "updated_fields" in detail:
                parts.append(f"Fields: {', '.join(detail['updated_fields'])}")
            elif "type" in detail:
                parts.append(f"Type: {detail['type']}")
            if detail.get("via") == "api":
                parts.append("via API")
            detail_str = _s("; ".join(parts))[:40]

            pdf.cell(w_date,   6, dt_str,      border=1)
            pdf.cell(w_user,   6, user_str,    border=1)
            pdf.cell(w_action, 6, action_str,  border=1)
            pdf.cell(w_detail, 6, detail_str,  border=1,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf_bytes = bytes(pdf.output())
    safe_name = "".join(c if c.isalnum() or c in "- " else "_" for c in resource.name)[:50].strip()
    filename = f"tribal-{safe_name}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{resource_id}/certificate", response_model=schemas.ResourceResponse)
async def upload_certificate(
    request: Request,
    resource_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_write_access),
):
    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} is not allowed. Only public certificates (.pem, .crt, .cer) are accepted.")

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .pem, .crt, and .cer files are allowed.")

    content = await file.read()

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read file contents.")

    for marker in PRIVATE_KEY_MARKERS:
        if marker in text:
            raise HTTPException(status_code=400, detail="Private keys are not allowed. Please upload only the public certificate.")

    expiry = extract_expiry_from_pem(content)
    if not expiry:
        raise HTTPException(status_code=400, detail="Could not parse certificate. Ensure the file is a valid PEM/DER certificate.")

    resource.public_key_pem = text
    resource.expiration_date = expiry
    resource.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resource)
    _audit(db, "resource.cert_upload", resource, current_user, {"expiration_date": expiry.isoformat()}, via=getattr(request.state, "auth_via", "ui"))
    return resource
