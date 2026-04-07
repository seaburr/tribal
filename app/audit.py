"""Shared audit log helper — usable by any router without circular imports."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from . import models

_log = logging.getLogger(__name__)


def write_audit(
    db: Session,
    action: str,
    *,
    user_email: Optional[str] = None,
    resource_id: Optional[int] = None,
    resource_name: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """Write an audit log entry. Silently swallows errors — auditing must never break the main flow."""
    try:
        db.add(models.AuditLog(
            user_email=user_email,
            resource_id=resource_id,
            resource_name=resource_name,
            action=action,
            detail=detail,
        ))
        db.commit()
    except Exception:
        _log.exception("Failed to write audit log for action %r", action)

