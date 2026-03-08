from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import decode_access_token, hash_api_key
from .database import get_db
from . import models

_COOKIE = "session"


def _user_from_request(request: Request, db: Session) -> Optional[models.User]:
    """Resolves a user from either a session cookie or a Bearer API key."""
    # 1. Session cookie
    token = request.cookies.get(_COOKIE)
    if token:
        user_id = decode_access_token(token)
        if user_id:
            return db.get(models.User, user_id)

    # 2. Bearer API key
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_key = auth_header[7:]
        key_hash = hash_api_key(raw_key)
        api_key = (
            db.query(models.ApiKey)
            .filter(
                models.ApiKey.key_hash == key_hash,
                models.ApiKey.revoked_at.is_(None),
            )
            .first()
        )
        if api_key:
            api_key.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return db.get(models.User, api_key.user_id)

    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user = _user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    """Returns the current user if authenticated, otherwise None. Never raises."""
    try:
        return _user_from_request(request, db)
    except Exception:
        return None


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user
