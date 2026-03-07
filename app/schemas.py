from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str]
    is_admin: bool = False

    model_config = {"from_attributes": True}


class AdminSettingsResponse(BaseModel):
    reminder_days: list[int]
    notify_hour: int

    model_config = {"from_attributes": True}


class AdminSettingsUpdate(BaseModel):
    reminder_days: list[int]
    notify_hour: int


class AuditLogEntry(BaseModel):
    id: int
    user_email: Optional[str]
    resource_id: Optional[int]
    resource_name: Optional[str]
    action: str
    detail: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


def _parse_date(v):
    if v is None:
        return v
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime as dt
                return dt.strptime(v, fmt).date()
            except ValueError:
                continue
        raise ValueError("Date must be in MM/DD/YYYY or YYYY-MM-DD format")
    return v


RESOURCE_TYPES = ["Certificate", "API Key", "SSH Key", "Other"]


class WebhookTestRequest(BaseModel):
    webhook_url: str


class ResourceCreate(BaseModel):
    name: str
    dri: str
    type: str
    expiration_date: date
    purpose: str
    generation_instructions: str
    secret_manager_link: Optional[str] = None
    slack_webhook: str

    @field_validator("expiration_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        return _parse_date(v)


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    dri: Optional[str] = None
    type: Optional[str] = None
    expiration_date: Optional[date] = None
    purpose: Optional[str] = None
    generation_instructions: Optional[str] = None
    secret_manager_link: Optional[str] = None
    slack_webhook: Optional[str] = None

    @field_validator("expiration_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        return _parse_date(v)


class ResourceResponse(BaseModel):
    id: int
    name: str
    dri: str
    type: str
    expiration_date: date
    purpose: str
    generation_instructions: str
    secret_manager_link: Optional[str]
    slack_webhook: str
    public_key_pem: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
