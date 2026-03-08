from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import generate_api_key, hash_api_key
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/keys", tags=["api-keys"])

_PREFIX_DISPLAY_LEN = 8  # chars shown after "tribal_sk_" in the UI


@router.get("/", response_model=list[schemas.ApiKeyResponse])
def list_keys(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.ApiKey)
        .filter(
            models.ApiKey.user_id == current_user.id,
            models.ApiKey.revoked_at.is_(None),
        )
        .order_by(models.ApiKey.created_at.desc())
        .all()
    )


@router.post("/", response_model=schemas.ApiKeyCreatedResponse, status_code=201)
def create_key(
    body: schemas.ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Key name cannot be empty.")

    raw_key = generate_api_key()
    # "tribal_sk_" is 10 chars; grab the next _PREFIX_DISPLAY_LEN chars for display
    prefix = raw_key[:10 + _PREFIX_DISPLAY_LEN] + "..."

    api_key = models.ApiKey(
        user_id=current_user.id,
        name=body.name.strip(),
        key_prefix=prefix,
        key_hash=hash_api_key(raw_key),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return schemas.ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        full_key=raw_key,
    )


@router.delete("/{key_id}", status_code=204)
def revoke_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    api_key = db.query(models.ApiKey).filter(
        models.ApiKey.id == key_id,
        models.ApiKey.user_id == current_user.id,
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found.")
    if api_key.revoked_at:
        raise HTTPException(status_code=400, detail="Key is already revoked.")

    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()
