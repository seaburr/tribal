from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user
from ..cert_utils import extract_expiry_from_pem, fetch_cert_expiry_from_endpoint
from ..scheduler import send_deletion_notification, _TRIBAL_FOOTER

router = APIRouter(prefix="/api/resources", tags=["resources"])

BLOCKED_EXTENSIONS = {".key", ".p12", ".p7b", ".pfx"}
ALLOWED_EXTENSIONS = {".pem", ".crt", ".cer"}
PRIVATE_KEY_MARKERS = ["PRIVATE KEY", "RSA PRIVATE", "EC PRIVATE", "ENCRYPTED PRIVATE", "DSA PRIVATE"]


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
    except httpx.RequestError as e:
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
    current_user: models.User = Depends(get_current_user),
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
    _audit(db, "resource.create", db_resource, current_user, {"type": db_resource.type}, via=getattr(request.state, "auth_via", "ui"))
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
    current_user: models.User = Depends(get_current_user),
):
    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resource, field, value)

    resource.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resource)
    _audit(db, "resource.update", resource, current_user, {"updated_fields": list(update_data.keys())}, via=getattr(request.state, "auth_via", "ui"))
    return resource


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    request: Request,
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resource = _active(db).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    _audit(db, "resource.delete", resource, current_user, {"type": resource.type, "dri": resource.dri}, via=getattr(request.state, "auth_via", "ui"))
    deleted_by = current_user.display_name or current_user.email if current_user else None
    await send_deletion_notification(resource, deleted_by=deleted_by)
    resource.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{resource_id}/certificate", response_model=schemas.ResourceResponse)
async def upload_certificate(
    request: Request,
    resource_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
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
