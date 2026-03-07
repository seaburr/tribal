import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

_log = logging.getLogger(__name__)

JWT_SECRET: str = os.environ.get("JWT_SECRET", "").strip()
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    _log.warning(
        "JWT_SECRET env var not set — using a randomly generated secret. "
        "Sessions will be invalidated on restart and will not work across "
        "multiple replicas. Set JWT_SECRET for stable sessions."
    )

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_DAYS = 7

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=_JWT_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        JWT_SECRET,
        algorithm=_JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return int(payload["sub"])
    except Exception:
        return None
