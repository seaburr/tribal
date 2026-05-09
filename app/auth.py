import hashlib
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_DAYS = 7
_JWT_SECRET_NAME = "jwt_signing_key"

# Cached signing key — populated on first read, invalidated on rotation.
_jwt_secret: Optional[str] = None
_jwt_lock = threading.Lock()


def _generate_secret() -> str:
    return secrets.token_urlsafe(64)


def _load_or_create_jwt_secret(db: Session) -> str:
    """Read the JWT signing key from the DB, creating it if missing.

    Caches in module-level state so subsequent calls avoid the DB hit.
    """
    from . import models  # local import to avoid circular at module load

    global _jwt_secret
    with _jwt_lock:
        if _jwt_secret is not None:
            return _jwt_secret
        row = (
            db.query(models.AppSecret)
            .filter(models.AppSecret.name == _JWT_SECRET_NAME)
            .first()
        )
        if row is None:
            row = models.AppSecret(name=_JWT_SECRET_NAME, value=_generate_secret())
            db.add(row)
            db.commit()
            db.refresh(row)
            _log.info("Generated initial JWT signing key and stored it in app_secrets.")
        _jwt_secret = row.value
        return _jwt_secret


def _get_jwt_secret() -> str:
    """Return the cached JWT signing key, loading it from the DB if necessary.

    Used by code paths that don't have a request-scoped Session (e.g. the
    auth middleware). Opens its own SessionLocal when the cache is empty.
    """
    global _jwt_secret
    if _jwt_secret is not None:
        return _jwt_secret
    from .database import SessionLocal

    db = SessionLocal()
    try:
        return _load_or_create_jwt_secret(db)
    finally:
        db.close()


def rotate_jwt_secret(db: Session) -> str:
    """Generate a new JWT signing key, persist it, and invalidate the cache.

    Returns the new value (caller should not log it). All existing sessions
    are invalidated; clients must log in again.
    """
    from . import models

    global _jwt_secret
    with _jwt_lock:
        new_value = _generate_secret()
        row = (
            db.query(models.AppSecret)
            .filter(models.AppSecret.name == _JWT_SECRET_NAME)
            .first()
        )
        if row is None:
            row = models.AppSecret(name=_JWT_SECRET_NAME, value=new_value)
            db.add(row)
        else:
            row.value = new_value
        db.commit()
        _jwt_secret = new_value
        return new_value


def _reset_jwt_secret_cache() -> None:
    """Test helper — clears the in-process cache."""
    global _jwt_secret
    with _jwt_lock:
        _jwt_secret = None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, db: Optional[Session] = None) -> str:
    """Issue a JWT for the given user.

    Pass `db` from a request handler so the signing key is loaded via the
    request-scoped session (needed during tests where the global
    SessionLocal points at a different database than the request).
    """
    secret = _load_or_create_jwt_secret(db) if db is not None else _get_jwt_secret()
    expire = datetime.now(timezone.utc) + timedelta(days=_JWT_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        secret,
        algorithm=_JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
        return int(payload["sub"])
    except Exception:
        return None


_API_KEY_PREFIX = "tribal_sk_"


def generate_api_key() -> str:
    """Return a new plaintext API key. Store only the hash, never this value."""
    return _API_KEY_PREFIX + secrets.token_hex(32)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
