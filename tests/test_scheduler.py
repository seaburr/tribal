"""Tests for Slack notification payload construction and scheduler logic."""
import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AdminSettings, Base, ReminderLog, Resource
from app.scheduler import (
    _send_slack_reminder,
    _send_overdue_alert,
    send_deletion_notification,
    check_reminders,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def resource():
    return Resource(
        id=1,
        name="Production TLS Certificate",
        dri="ops@example.com",
        type="Certificate",
        expiration_date=date.today() + timedelta(days=14),
        purpose="Secures the production API endpoint.",
        generation_instructions="Run certbot renew --cert-name api.example.com",
        slack_webhook="https://hooks.slack.com/services/TEST/TEST/TEST",
        secret_manager_link=None,
    )


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _make_mock_client(status_code=200):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ── _send_slack_reminder ──────────────────────────────────────────────────────

def test_reminder_payload_structure(resource):
    """Verify the reminder Slack payload has the expected blocks."""
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 14))

    payload = mock_client.post.call_args[1]["json"]
    assert resource.name in payload["text"]
    assert "14" in payload["text"]
    block_types = [b["type"] for b in payload["blocks"]]
    assert "header" in block_types
    assert "context" in block_types  # Tribal footer
    header = next(b for b in payload["blocks"] if b["type"] == "header")
    assert resource.name in header["text"]["text"]


def test_reminder_urgent_prefix_3_days(resource):
    resource.expiration_date = date.today() + timedelta(days=3)
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 3))

    payload = mock_client.post.call_args[1]["json"]
    assert "URGENT" in payload["text"]
    assert "URGENT" in payload["blocks"][0]["text"]["text"]


def test_reminder_warning_prefix_7_days(resource):
    resource.expiration_date = date.today() + timedelta(days=7)
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 7))

    payload = mock_client.post.call_args[1]["json"]
    assert "URGENT" not in payload["text"]


def test_reminder_no_urgency_prefix_30_days(resource):
    resource.expiration_date = date.today() + timedelta(days=30)
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 30))

    payload = mock_client.post.call_args[1]["json"]
    assert "URGENT" not in payload["text"]
    assert "URGENT" not in payload["blocks"][0]["text"]["text"]


def test_reminder_singular_day(resource):
    resource.expiration_date = date.today() + timedelta(days=1)
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 1))

    payload = mock_client.post.call_args[1]["json"]
    assert "1 day" in payload["text"]
    assert "1 days" not in payload["text"]


def test_reminder_includes_secret_link(resource):
    resource.secret_manager_link = "https://vault.example.com/secret"
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 14))

    payload = mock_client.post.call_args[1]["json"]
    full_text = str(payload)
    assert "vault.example.com" in full_text


def test_reminder_omits_secret_link_when_absent(resource):
    resource.secret_manager_link = None
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 14))

    payload = mock_client.post.call_args[1]["json"]
    assert "Secret Manager" not in str(payload)


def test_reminder_posts_to_resource_webhook(resource):
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_slack_reminder(resource, 14))

    url = mock_client.post.call_args[0][0]
    assert url == resource.slack_webhook


def test_reminder_silences_http_errors(resource):
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("network error"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        # Should not raise
        asyncio.run(_send_slack_reminder(resource, 14))


# ── _send_overdue_alert ───────────────────────────────────────────────────────

def test_overdue_alert_payload(resource):
    resource.expiration_date = date.today() - timedelta(days=5)
    admin_webhook = "https://hooks.slack.com/services/ADMIN/ADMIN/ADMIN"
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_overdue_alert(resource, admin_webhook))

    payload = mock_client.post.call_args[1]["json"]
    assert "OVERDUE" in payload["text"]
    assert resource.name in payload["text"]
    header = next(b for b in payload["blocks"] if b["type"] == "header")
    assert "OVERDUE" in header["text"]["text"]
    assert resource.name in header["text"]["text"]


def test_overdue_alert_posts_to_admin_webhook(resource):
    resource.expiration_date = date.today() - timedelta(days=3)
    admin_webhook = "https://hooks.slack.com/services/ADMIN/WEBHOOK"
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(_send_overdue_alert(resource, admin_webhook))

    url = mock_client.post.call_args[0][0]
    assert url == admin_webhook


# ── send_deletion_notification ────────────────────────────────────────────────

def test_deletion_notification_payload(resource):
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(send_deletion_notification(resource))

    payload = mock_client.post.call_args[1]["json"]
    assert resource.name in payload["text"]
    header = next(b for b in payload["blocks"] if b["type"] == "header")
    assert resource.name in header["text"]["text"]
    assert "deleted" in header["text"]["text"].lower()


def test_deletion_notification_posts_to_resource_webhook(resource):
    with patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(send_deletion_notification(resource))

    url = mock_client.post.call_args[0][0]
    assert url == resource.slack_webhook


# ── check_reminders ───────────────────────────────────────────────────────────

def test_check_reminders_skips_wrong_hour(db_session):
    """check_reminders does nothing outside the configured notify_hour."""
    settings = AdminSettings(id=1, reminder_days=[14], notify_hour=9)
    db_session.add(settings)
    db_session.commit()

    with patch("app.scheduler.SessionLocal", return_value=db_session), \
         patch("app.scheduler.datetime") as mock_dt, \
         patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_dt.now.return_value.hour = 10  # wrong hour
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        asyncio.run(check_reminders())

    mock_client.post.assert_not_called()


def test_check_reminders_sends_and_deduplicates(db_session):
    """Sends a reminder at the right hour and skips it on the second run."""
    today = date.today()
    settings = AdminSettings(id=1, reminder_days=[14], notify_hour=9)
    r = Resource(
        id=10,
        name="Test Resource",
        dri="dri@example.com",
        type="API Key",
        expiration_date=today + timedelta(days=14),
        purpose="Test",
        generation_instructions="Rotate it",
        slack_webhook="https://hooks.slack.com/TEST",
    )
    db_session.add(settings)
    db_session.add(r)
    db_session.commit()

    with patch("app.scheduler.SessionLocal", return_value=db_session), \
         patch("app.scheduler.datetime") as mock_dt, \
         patch("app.scheduler.date") as mock_date, \
         patch("app.scheduler.httpx.AsyncClient") as mock_cls:
        mock_dt.now.return_value.hour = 9
        mock_date.today.return_value = today
        mock_client = _make_mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        asyncio.run(check_reminders())
        assert mock_client.post.call_count == 1

        # Second run — already logged, should not send again
        asyncio.run(check_reminders())
        assert mock_client.post.call_count == 1
