from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user
from ..cert_utils import extract_expiry_from_pem
from ..scheduler import send_deletion_notification

router = APIRouter(prefix="/api/resources", tags=["resources"])

BLOCKED_EXTENSIONS = {".key", ".p12", ".p7b", ".pfx"}
ALLOWED_EXTENSIONS = {".pem", ".crt", ".cer"}
PRIVATE_KEY_MARKERS = ["PRIVATE KEY", "RSA PRIVATE", "EC PRIVATE", "ENCRYPTED PRIVATE", "DSA PRIVATE"]


def _audit(db: Session, action: str, resource: models.Resource, user: Optional[models.User], detail: Optional[dict] = None):
    try:
        entry = models.AuditLog(
            user_email=user.email if user else None,
            resource_id=resource.id,
            resource_name=resource.name,
            action=action,
            detail=detail,
        )
        db.add(entry)
        db.commit()
    except Exception:
        pass  # audit logging must never break the main flow


@router.post("/webhook-test", status_code=204)
async def test_webhook(
    req: schemas.WebhookTestRequest,
    _: models.User = Depends(get_current_user),
):
    payload = {"text": "This is a test message from Tribal."}
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
    return db.query(models.Resource).order_by(models.Resource.expiration_date).all()


@router.post("/", response_model=schemas.ResourceResponse, status_code=201)
def create_resource(
    resource: schemas.ResourceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_resource = models.Resource(**resource.model_dump())
    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)
    _audit(db, "resource.create", db_resource, current_user, {"type": db_resource.type})
    return db_resource


@router.get("/{resource_id}", response_model=schemas.ResourceResponse)
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.put("/{resource_id}", response_model=schemas.ResourceResponse)
def update_resource(
    resource_id: int,
    updates: schemas.ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resource, field, value)

    resource.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resource)
    _audit(db, "resource.update", resource, current_user, {"updated_fields": list(update_data.keys())})
    return resource


@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    _audit(db, "resource.delete", resource, current_user, {"type": resource.type, "dri": resource.dri})
    await send_deletion_notification(resource)
    db.delete(resource)
    db.commit()


@router.post("/{resource_id}/certificate", response_model=schemas.ResourceResponse)
async def upload_certificate(
    resource_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resource = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
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
    _audit(db, "resource.cert_upload", resource, current_user, {"expiration_date": expiry.isoformat()})
    return resource
