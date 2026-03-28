from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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
    is_account_creator: bool = False
    is_readonly: bool = False

    model_config = {"from_attributes": True}


class AdminSettingsResponse(BaseModel):
    org_name: Optional[str] = None
    reminder_days: list[int]
    notify_hour: int
    slack_webhook: Optional[str] = None
    alert_on_overdue: bool = False
    alert_on_delete: bool = False
    review_cadence_months: Optional[int] = None

    model_config = {"from_attributes": True}


class AdminSettingsUpdate(BaseModel):
    org_name: Optional[str] = None
    reminder_days: list[int]
    notify_hour: int
    slack_webhook: Optional[str] = None
    alert_on_overdue: bool = False
    alert_on_delete: bool = False
    review_cadence_months: Optional[int] = None


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogEntry(BaseModel):
    id: int
    user_email: Optional[str]
    resource_id: Optional[int]
    resource_name: Optional[str]
    action: str
    detail: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str = Field(max_length=255)


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned once on creation — includes the full plaintext key."""
    full_key: str


class ApiKeyAdminResponse(ApiKeyResponse):
    """Used by admin endpoint — includes owner email."""
    user_email: str


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

_TYPE_DISPLAY_MAP: dict[str, str] = {
    "api_key": "API Key",
    "certificate": "Certificate",
    "ssh_key": "SSH Key",
    "other": "Other",
}


def normalize_resource_type(v: str) -> str:
    """Normalize snake_case type variants to their display names."""
    return _TYPE_DISPLAY_MAP.get(v.lower().replace(" ", "_"), v)


class WebhookTestRequest(BaseModel):
    webhook_url: str


class CertLookupRequest(BaseModel):
    endpoint: str


class CertLookupResponse(BaseModel):
    expiration_date: date


class ResourceCreate(BaseModel):
    name: str
    dri: str
    type: str
    expiration_date: Optional[date] = None
    does_not_expire: bool = False
    purpose: str
    generation_instructions: str
    secret_manager_link: Optional[str] = None
    slack_webhook: str
    team_id: Optional[int] = None
    certificate_url: Optional[str] = None
    auto_refresh_expiry: bool = False

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        return normalize_resource_type(v) if isinstance(v, str) else v

    @field_validator("expiration_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        return _parse_date(v)

    @model_validator(mode="after")
    def require_date_unless_no_expiry(self):
        if not self.does_not_expire and self.expiration_date is None:
            raise ValueError("Expiration date is required unless 'does_not_expire' is set.")
        if self.does_not_expire:
            self.expiration_date = None
        return self


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    dri: Optional[str] = None
    type: Optional[str] = None
    expiration_date: Optional[date] = None
    does_not_expire: Optional[bool] = None
    purpose: Optional[str] = None
    generation_instructions: Optional[str] = None
    secret_manager_link: Optional[str] = None
    slack_webhook: Optional[str] = None
    team_id: Optional[int] = None
    certificate_url: Optional[str] = None
    auto_refresh_expiry: Optional[bool] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v):
        return normalize_resource_type(v) if isinstance(v, str) else v

    @field_validator("expiration_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        return _parse_date(v)


class ResourceResponse(BaseModel):
    id: int
    name: str
    dri: str
    type: str
    expiration_date: Optional[date] = None
    does_not_expire: bool = False
    purpose: str
    generation_instructions: str
    secret_manager_link: Optional[str]
    slack_webhook: str
    team_id: Optional[int] = None
    public_key_pem: Optional[str]
    certificate_url: Optional[str] = None
    auto_refresh_expiry: bool = False
    last_reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeletedResourceResponse(ResourceResponse):
    deleted_at: datetime
