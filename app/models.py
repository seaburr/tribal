from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    is_account_creator = Column(Boolean, nullable=False, default=False)
    is_readonly = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow)


class AdminSettings(Base):
    """Singleton row (id=1) storing org-wide admin configuration."""
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, default=1)
    org_name = Column(String(255), nullable=True)
    reminder_days = Column(JSON, nullable=False, default=lambda: [30, 14, 7, 3])
    notify_hour = Column(Integer, nullable=False, default=9)
    slack_webhook = Column(String(500), nullable=True)
    alert_on_overdue = Column(Boolean, nullable=False, default=False)
    alert_on_delete = Column(Boolean, nullable=False, default=False)
    review_cadence_months = Column(Integer, nullable=True, default=None)
    updated_at = Column(DateTime, default=_utcnow)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=True)
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(255), nullable=True)
    action = Column(String(64), nullable=False)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(32), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime, default=_utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    dri = Column(String(255), nullable=False)
    expiration_date = Column(Date, nullable=True)
    does_not_expire = Column(Boolean, nullable=False, default=False)
    purpose = Column(Text, nullable=False)
    generation_instructions = Column(Text, nullable=False)
    secret_manager_link = Column(String(1000), nullable=True)
    slack_webhook = Column(String(500), nullable=False)
    type = Column(String(50), nullable=False, server_default="Other")
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    public_key_pem = Column(Text, nullable=True)
    certificate_url = Column(String(1000), nullable=True)
    auto_refresh_expiry = Column(Boolean, nullable=False, default=False)
    last_reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow)
    deleted_at = Column(DateTime, nullable=True, default=None)


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    expiration_date = Column(Date, nullable=False)
    days_before = Column(Integer, nullable=False)
    reminder_type = Column(String(20), nullable=False, server_default="expiry")
    sent_at = Column(DateTime, default=_utcnow)
