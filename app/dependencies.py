from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import decode_access_token
from .database import get_db
from . import models

_COOKIE = "session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    token = request.cookies.get(_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    """Returns the current user if authenticated, otherwise None. Never raises."""
    try:
        token = request.cookies.get(_COOKIE)
        if not token:
            return None
        user_id = decode_access_token(token)
        if not user_id:
            return None
        return db.get(models.User, user_id)
    except Exception:
        return None


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user
