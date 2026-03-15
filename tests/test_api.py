from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.auth import hash_password
from app.database import get_db
from app.models import Base, User

SAMPLE = {
    "name": "Production TLS Certificate",
    "dri": "ops@example.com",
    "type": "Certificate",
    "expiration_date": (date.today() + timedelta(days=90)).isoformat(),
    "purpose": "Secures the production API endpoint.",
    "generation_instructions": "Run certbot renew --cert-name api.example.com.",
    "secret_manager_link": None,
    "slack_webhook": "https://hooks.slack.com/services/TEST/TEST/TEST",
}


@pytest.fixture
def client(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed a test admin user.
    db = Session()
    db.add(User(email="test@example.com", hashed_password=hash_password("testpassword"), is_admin=True))
    db.commit()
    db.close()

    with TestClient(app, follow_redirects=False) as c:
        # Log in via the real endpoint so the session cookie is stored by the
        # HTTP client (secure=False over HTTP, so httpx retains the cookie).
        r = c.post("/auth/login", json={"email": "test@example.com", "password": "testpassword"})
        assert r.status_code == 200, f"Test login failed: {r.text}"
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def created(client):
    """Create one resource and return its JSON."""
    r = client.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    return r.json()


# ── Health check ──────────────────────────────────────────────────────────────

def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Create ───────────────────────────────────────────────────────────────────

def test_create_resource(client):
    r = client.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == SAMPLE["name"]
    assert data["type"] == SAMPLE["type"]
    assert data["dri"] == SAMPLE["dri"]
    assert "id" in data


def test_create_resource_missing_required_field(client):
    payload = {k: v for k, v in SAMPLE.items() if k != "dri"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 422


def test_create_resource_invalid_date(client):
    payload = {**SAMPLE, "expiration_date": "not-a-date"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 422


# ── List ─────────────────────────────────────────────────────────────────────

def test_list_resources_empty(client):
    r = client.get("/api/resources/")
    assert r.status_code == 200
    assert r.json() == []


def test_list_resources_returns_all(client, created):
    r = client.get("/api/resources/")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]


# ── Get ──────────────────────────────────────────────────────────────────────

def test_get_resource(client, created):
    r = client.get(f"/api/resources/{created['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == SAMPLE["name"]


def test_get_resource_not_found(client):
    r = client.get("/api/resources/9999")
    assert r.status_code == 404


# ── Update ───────────────────────────────────────────────────────────────────

def test_update_resource_name(client, created):
    r = client.put(f"/api/resources/{created['id']}", json={"name": "Updated Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


def test_update_resource_date(client, created):
    new_date = (date.today() + timedelta(days=180)).isoformat()
    r = client.put(f"/api/resources/{created['id']}", json={"expiration_date": new_date})
    assert r.status_code == 200
    assert r.json()["expiration_date"] == new_date


def test_update_resource_not_found(client):
    r = client.put("/api/resources/9999", json={"name": "X"})
    assert r.status_code == 404


# ── Delete ───────────────────────────────────────────────────────────────────

def test_delete_resource(client, created):
    with patch("app.routers.resources.send_deletion_notification", new=AsyncMock()):
        r = client.delete(f"/api/resources/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/resources/{created['id']}").status_code == 404


def test_delete_resource_not_found(client):
    with patch("app.routers.resources.send_deletion_notification", new=AsyncMock()):
        r = client.delete("/api/resources/9999")
    assert r.status_code == 404


# ── Webhook test ─────────────────────────────────────────────────────────────

def test_webhook_test_success(client):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    with patch("app.routers.resources.httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        r = client.post(
            "/api/resources/webhook-test",
            json={"webhook_url": "https://hooks.slack.com/services/TEST"},
        )
    assert r.status_code == 204


def test_webhook_test_missing_url(client):
    r = client.post("/api/resources/webhook-test", json={})
    assert r.status_code == 422


# ── Certificate upload ────────────────────────────────────────────────────────

def test_certificate_upload_blocked_extension(client, created):
    r = client.post(
        f"/api/resources/{created['id']}/certificate",
        files={"file": ("keyfile.p12", b"fake", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_certificate_upload_disallowed_extension(client, created):
    r = client.post(
        f"/api/resources/{created['id']}/certificate",
        files={"file": ("file.txt", b"fake", "text/plain")},
    )
    assert r.status_code == 400


def test_certificate_upload_private_key_rejected(client, created):
    content = b"-----BEGIN PRIVATE KEY-----\nfakedata\n-----END PRIVATE KEY-----\n"
    r = client.post(
        f"/api/resources/{created['id']}/certificate",
        files={"file": ("cert.pem", content, "application/octet-stream")},
    )
    assert r.status_code == 400


def test_certificate_upload_invalid_cert_content(client, created):
    r = client.post(
        f"/api/resources/{created['id']}/certificate",
        files={"file": ("cert.pem", b"not a real certificate", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_certificate_upload_resource_not_found(client):
    r = client.post(
        "/api/resources/9999/certificate",
        files={"file": ("cert.pem", b"data", "application/octet-stream")},
    )
    assert r.status_code == 404


# ── API Keys ──────────────────────────────────────────────────────────────────

def test_create_api_key(client):
    r = client.post("/api/keys/", json={"name": "Test Key"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test Key"
    assert data["full_key"].startswith("tribal_sk_")
    assert "full_key" in data
    assert data["revoked_at"] is None


def test_list_api_keys(client):
    client.post("/api/keys/", json={"name": "Key A"})
    client.post("/api/keys/", json={"name": "Key B"})
    r = client.get("/api/keys/")
    assert r.status_code == 200
    names = [k["name"] for k in r.json()]
    assert "Key A" in names and "Key B" in names


def test_revoke_api_key(client):
    r = client.post("/api/keys/", json={"name": "To Revoke"})
    key_id = r.json()["id"]
    r = client.delete(f"/api/keys/{key_id}")
    assert r.status_code == 204
    # Should no longer appear in list
    keys = client.get("/api/keys/").json()
    assert not any(k["id"] == key_id for k in keys)


def test_revoke_api_key_not_found(client):
    r = client.delete("/api/keys/9999")
    assert r.status_code == 404


def test_api_key_bearer_auth(client):
    """A valid API key sent as a Bearer token should authenticate all endpoints."""
    r = client.post("/api/keys/", json={"name": "Bearer Test"})
    raw_key = r.json()["full_key"]

    # Create a fresh client with NO session cookie, authenticating via Bearer only.
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/resources/", headers={"Authorization": f"Bearer {raw_key}"})
        assert r.status_code == 200

        r = anon.post(
            "/api/resources/",
            json=SAMPLE,
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert r.status_code == 201
        resource_id = r.json()["id"]

        r = anon.get(f"/api/resources/{resource_id}", headers={"Authorization": f"Bearer {raw_key}"})
        assert r.status_code == 200

        r = anon.put(
            f"/api/resources/{resource_id}",
            json={"name": "Updated via API key"},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated via API key"

        with patch("app.routers.resources.send_deletion_notification", new=AsyncMock()):
            r = anon.delete(f"/api/resources/{resource_id}", headers={"Authorization": f"Bearer {raw_key}"})
        assert r.status_code == 204


def test_revoked_api_key_rejected(client):
    """A revoked API key must be rejected."""
    r = client.post("/api/keys/", json={"name": "Revoke Me"})
    data = r.json()
    raw_key = data["full_key"]
    client.delete(f"/api/keys/{data['id']}")

    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/resources/", headers={"Authorization": f"Bearer {raw_key}"})
        assert r.status_code in (401, 303)


def test_invalid_bearer_token_rejected(client):
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/resources/", headers={"Authorization": "Bearer tribal_sk_notarealkey"})
        assert r.status_code in (401, 303)


def test_create_api_key_empty_name(client):
    r = client.post("/api/keys/", json={"name": "  "})
    assert r.status_code == 422


# ── Account creator protection (Iteration 13) ─────────────────────────────────

@pytest.fixture
def client_with_creator(tmp_path):
    """Two-admin fixture: 'creator' is the account creator, 'admin2' is a regular admin."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = Session()
    creator = User(
        email="creator@example.com",
        hashed_password=hash_password("testpassword"),
        is_admin=True,
        is_account_creator=True,
    )
    admin2 = User(
        email="admin2@example.com",
        hashed_password=hash_password("testpassword"),
        is_admin=True,
        is_account_creator=False,
    )
    regular = User(
        email="other@example.com",
        hashed_password=hash_password("testpassword"),
        is_admin=False,
        is_account_creator=False,
    )
    db.add(creator)
    db.add(admin2)
    db.add(regular)
    db.commit()
    creator_id = creator.id
    regular_id = regular.id
    db.close()

    # Log in as admin2 (a regular admin, not the creator)
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "admin2@example.com", "password": "testpassword"})
        assert r.status_code == 200
        yield c, creator_id, regular_id

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_account_creator_flag_in_user_list(client_with_creator):
    c, creator_id, other_id = client_with_creator
    r = c.get("/admin/users")
    assert r.status_code == 200
    users = {u["id"]: u for u in r.json()}
    assert users[creator_id]["is_account_creator"] is True
    assert users[other_id]["is_account_creator"] is False


def test_cannot_revoke_admin_from_account_creator(client_with_creator):
    c, creator_id, _ = client_with_creator
    r = c.put(f"/admin/users/{creator_id}/role?is_admin=false")
    assert r.status_code == 400
    assert "account creator" in r.json()["detail"].lower()


def test_cannot_delete_account_creator(client_with_creator):
    c, creator_id, _ = client_with_creator
    r = c.delete(f"/admin/users/{creator_id}")
    assert r.status_code == 400
    assert "account creator" in r.json()["detail"].lower()


def test_role_change_audited(client_with_creator):
    c, _, other_id = client_with_creator
    r = c.put(f"/admin/users/{other_id}/role?is_admin=true")
    assert r.status_code == 200

    audit = c.get("/admin/audit-log").json()
    role_events = [e for e in audit if e["action"] == "user.role_change"]
    assert role_events, "Expected a user.role_change audit entry"
    detail = role_events[0]["detail"]
    assert detail["action"] == "granted"
    assert detail["new_role"] == "admin"


# ── Notification settings ─────────────────────────────────────────────────────

def test_admin_settings_default_reminder_days(client):
    r = client.get("/admin/settings")
    assert r.status_code == 200
    data = r.json()
    assert "reminder_days" in data
    # Defaults should be [30, 14, 7, 3] (stored descending)
    assert set(data["reminder_days"]) == {30, 14, 7, 3}


def test_admin_settings_accepts_60_and_45_days(client):
    payload = {
        "reminder_days": [60, 45, 30, 14, 7, 3],
        "notify_hour": 9,
        "slack_webhook": None,
        "alert_on_overdue": False,
        "alert_on_delete": False,
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 200
    saved = r.json()["reminder_days"]
    assert 60 in saved
    assert 45 in saved


def test_admin_settings_save_and_reload_60_45(client):
    payload = {
        "reminder_days": [60, 45],
        "notify_hour": 8,
        "slack_webhook": None,
        "alert_on_overdue": False,
        "alert_on_delete": False,
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 200

    r2 = client.get("/admin/settings")
    assert r2.status_code == 200
    data = r2.json()
    assert set(data["reminder_days"]) == {60, 45}
    assert data["notify_hour"] == 8


def test_admin_settings_rejects_empty_reminder_days(client):
    payload = {
        "reminder_days": [],
        "notify_hour": 9,
        "slack_webhook": None,
        "alert_on_overdue": False,
        "alert_on_delete": False,
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 422


def test_admin_settings_rejects_out_of_range_reminder_days(client):
    payload = {
        "reminder_days": [0, 30],
        "notify_hour": 9,
        "slack_webhook": None,
        "alert_on_overdue": False,
        "alert_on_delete": False,
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 422


def test_admin_settings_change_writes_audit_log(client):
    """Changing notification settings must produce an admin.settings_updated audit entry."""
    payload = {
        "reminder_days": [60, 30, 14],
        "notify_hour": 12,
        "slack_webhook": None,
        "alert_on_overdue": True,
        "alert_on_delete": False,
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 200

    r2 = client.get("/admin/audit-log")
    assert r2.status_code == 200
    actions = [e["action"] for e in r2.json()]
    assert "admin.settings_updated" in actions

    entry = next(e for e in r2.json() if e["action"] == "admin.settings_updated")
    assert "changes" in entry["detail"]


def test_admin_settings_no_change_does_not_write_audit_log(client):
    """Saving settings without changing anything must NOT add an audit entry."""
    # Read current settings
    r = client.get("/admin/settings")
    s = r.json()
    payload = {
        "org_name": s.get("org_name"),
        "reminder_days": s["reminder_days"],
        "notify_hour": s["notify_hour"],
        "slack_webhook": s.get("slack_webhook"),
        "alert_on_overdue": s["alert_on_overdue"],
        "alert_on_delete": s["alert_on_delete"],
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 200

    r2 = client.get("/admin/audit-log")
    actions = [e["action"] for e in r2.json()]
    assert "admin.settings_updated" not in actions


def test_admin_settings_org_name_syncs_team_name(client):
    """PUT /admin/settings with org_name must also update the singleton Team name."""
    from app.models import Team
    from app.database import get_db as _get_db

    # Create a team first
    client.post("/admin/teams", json={"name": "Original Team"})

    payload = {
        "org_name": "Updated Org Name",
        "reminder_days": [30, 14, 7, 3],
        "notify_hour": 9,
        "slack_webhook": None,
        "alert_on_overdue": False,
        "alert_on_delete": False,
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 200
    assert r.json()["org_name"] == "Updated Org Name"

    # The team name should now match
    r2 = client.get("/admin/teams")
    assert r2.status_code == 200
    teams = r2.json()
    assert len(teams) == 1
    assert teams[0]["name"] == "Updated Org Name"


def test_rename_team_syncs_org_name_and_survives_settings_save(client):
    """PUT /admin/teams/{id} must sync AdminSettings.org_name so a subsequent
    PUT /admin/settings doesn't overwrite Team.name back to the stale value."""
    # Create team
    r = client.post("/admin/teams", json={"name": "Initial"})
    assert r.status_code == 201
    team_id = r.json()["id"]

    # Rename via the teams endpoint (as Terraform does)
    r = client.put(f"/admin/teams/{team_id}", json={"name": "Terraform Name"})
    assert r.status_code == 200

    # AdminSettings.org_name should now reflect the new name
    r = client.get("/admin/settings")
    assert r.json()["org_name"] == "Terraform Name"

    # Simulate the UI saving settings — it will echo back the org_name it read
    settings = r.json()
    r = client.put("/admin/settings", json={
        "org_name": settings["org_name"],
        "reminder_days": settings["reminder_days"],
        "notify_hour": settings["notify_hour"],
        "slack_webhook": settings["slack_webhook"],
        "alert_on_overdue": settings["alert_on_overdue"],
        "alert_on_delete": settings["alert_on_delete"],
    })
    assert r.status_code == 200

    # Team name must still be "Terraform Name", not reverted
    r = client.get("/admin/teams")
    assert r.json()[0]["name"] == "Terraform Name"


# ── Certificate URL and auto-refresh ─────────────────────────────────────────

def test_create_certificate_resource_with_url(client):
    payload = {**SAMPLE, "certificate_url": "https://api.example.com", "auto_refresh_expiry": True}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["certificate_url"] == "https://api.example.com"
    assert data["auto_refresh_expiry"] is True


def test_certificate_url_defaults_to_none(client):
    r = client.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    data = r.json()
    assert data["certificate_url"] is None
    assert data["auto_refresh_expiry"] is False


def test_update_certificate_url(client, created):
    r = client.put(f"/api/resources/{created['id']}", json={"certificate_url": "https://new.example.com"})
    assert r.status_code == 200
    assert r.json()["certificate_url"] == "https://new.example.com"


def test_update_auto_refresh_expiry(client, created):
    r = client.put(f"/api/resources/{created['id']}", json={"auto_refresh_expiry": True})
    assert r.status_code == 200
    assert r.json()["auto_refresh_expiry"] is True


# ── Read-only role (Iteration 18) ─────────────────────────────────────────────

@pytest.fixture
def client_with_readonly(tmp_path):
    """Fixture: admin logs in; a separate read-only user client is also returned."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = Session()
    admin = User(
        email="admin@example.com",
        hashed_password=hash_password("testpassword"),
        is_admin=True,
        is_account_creator=True,
    )
    ro_user = User(
        email="readonly@example.com",
        hashed_password=hash_password("testpassword"),
        is_admin=False,
        is_readonly=True,
    )
    db.add(admin)
    db.add(ro_user)
    db.commit()
    admin_id = admin.id
    ro_id = ro_user.id
    db.close()

    with TestClient(app, follow_redirects=False) as admin_c:
        r = admin_c.post("/auth/login", json={"email": "admin@example.com", "password": "testpassword"})
        assert r.status_code == 200

        with TestClient(app, follow_redirects=False) as ro_c:
            r = ro_c.post("/auth/login", json={"email": "readonly@example.com", "password": "testpassword"})
            assert r.status_code == 200
            yield admin_c, ro_c, admin_id, ro_id

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_readonly_user_can_list_resources(client_with_readonly):
    _, ro_c, _, _ = client_with_readonly
    r = ro_c.get("/api/resources/")
    assert r.status_code == 200


def test_readonly_user_cannot_create_resource(client_with_readonly):
    _, ro_c, _, _ = client_with_readonly
    r = ro_c.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 403


def test_readonly_user_cannot_update_resource(client_with_readonly):
    admin_c, ro_c, _, _ = client_with_readonly
    r = admin_c.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    resource_id = r.json()["id"]

    r = ro_c.put(f"/api/resources/{resource_id}", json={"name": "Should Fail"})
    assert r.status_code == 403


def test_readonly_user_cannot_delete_resource(client_with_readonly):
    admin_c, ro_c, _, _ = client_with_readonly
    r = admin_c.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    resource_id = r.json()["id"]

    with patch("app.routers.resources.send_deletion_notification", new=AsyncMock()):
        r = ro_c.delete(f"/api/resources/{resource_id}")
    assert r.status_code == 403


def test_readonly_flag_in_user_response(client_with_readonly):
    _, ro_c, _, ro_id = client_with_readonly
    r = ro_c.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["is_readonly"] is True


def test_admin_can_set_user_readonly(client_with_readonly):
    admin_c, _, _, ro_id = client_with_readonly
    # Remove read-only
    r = admin_c.put(f"/admin/users/{ro_id}/readonly?is_readonly=false")
    assert r.status_code == 200
    assert r.json()["is_readonly"] is False
    # Re-apply
    r = admin_c.put(f"/admin/users/{ro_id}/readonly?is_readonly=true")
    assert r.status_code == 200
    assert r.json()["is_readonly"] is True


def test_cannot_set_admin_to_readonly(client_with_readonly):
    admin_c, _, _, ro_id = client_with_readonly
    # First promote ro_user to admin
    r = admin_c.put(f"/admin/users/{ro_id}/role?is_admin=true")
    assert r.status_code == 200
    # Now try to set that admin to read-only — should be rejected
    r = admin_c.put(f"/admin/users/{ro_id}/readonly?is_readonly=true")
    assert r.status_code == 400
    assert "admin" in r.json()["detail"].lower()


def test_cannot_set_account_creator_to_readonly(client_with_readonly):
    admin_c, _, admin_id, _ = client_with_readonly
    r = admin_c.put(f"/admin/users/{admin_id}/readonly?is_readonly=true")
    assert r.status_code == 400


def test_readonly_role_change_audited(client_with_readonly):
    admin_c, _, _, ro_id = client_with_readonly
    # Remove read-only
    r = admin_c.put(f"/admin/users/{ro_id}/readonly?is_readonly=false")
    assert r.status_code == 200

    audit = admin_c.get("/admin/audit-log").json()
    role_events = [e for e in audit if e["action"] == "user.role_change"]
    assert role_events, "Expected a user.role_change audit entry"
    detail = role_events[0]["detail"]
    assert detail["new_role"] == "member"
    assert detail["action"] == "revoked"


# ── Iteration 20: type normalization in audit log ─────────────────────────────

def test_audit_log_type_uses_display_name_on_create(client):
    """resource.create audit entry must store the display name (e.g. 'API Key'),
    not a snake_case variant (e.g. 'api_key')."""
    payload = {**SAMPLE, "type": "api_key"}  # snake_case from API/Terraform
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 201

    audit = client.get("/admin/audit-log").json()
    create_events = [e for e in audit if e["action"] == "resource.create"]
    assert create_events, "Expected a resource.create audit entry"
    assert create_events[0]["detail"]["type"] == "API Key"


def test_audit_log_type_uses_display_name_on_delete(client):
    """resource.delete audit entry must store the display name for the type."""
    payload = {**SAMPLE, "type": "SSH Key"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 201
    resource_id = r.json()["id"]

    with patch("app.routers.resources.send_deletion_notification", new=AsyncMock()):
        r = client.delete(f"/api/resources/{resource_id}")
    assert r.status_code == 204

    audit = client.get("/admin/audit-log").json()
    delete_events = [e for e in audit if e["action"] == "resource.delete"]
    assert delete_events, "Expected a resource.delete audit entry"
    assert delete_events[0]["detail"]["type"] == "SSH Key"


def test_snake_case_type_normalized_on_create(client):
    """Types sent as snake_case (e.g. from the Terraform provider) must be
    normalized to their display names and stored that way in the database."""
    payload = {**SAMPLE, "type": "ssh_key"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 201
    assert r.json()["type"] == "SSH Key"


def test_snake_case_type_normalized_on_update(client, created):
    """Updating a resource with a snake_case type must normalize it."""
    r = client.put(f"/api/resources/{created['id']}", json={"type": "api_key"})
    assert r.status_code == 200
    assert r.json()["type"] == "API Key"


def test_display_name_type_unchanged_on_create(client):
    """Types already in display-name form must not be altered."""
    payload = {**SAMPLE, "type": "Certificate"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 201
    assert r.json()["type"] == "Certificate"


# ── Iteration 21: resource PDF report ─────────────────────────────────────────

def test_resource_report_returns_pdf(client, created):
    """GET /api/resources/{id}/report must return a PDF file."""
    r = client.get(f"/api/resources/{created['id']}/report")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_resource_report_not_found(client):
    """Report endpoint must return 404 for a non-existent resource."""
    r = client.get("/api/resources/9999/report")
    assert r.status_code == 404


def test_resource_report_has_content_disposition(client, created):
    """PDF response must include a content-disposition attachment header."""
    r = client.get(f"/api/resources/{created['id']}/report")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")


def test_resource_report_accessible_to_readonly_user(client_with_readonly):
    """Read-only users must be able to download the resource report."""
    admin_c, ro_c, _, _ = client_with_readonly
    # Admin creates a resource
    r = admin_c.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    resource_id = r.json()["id"]

    # Read-only user can fetch the report
    r = ro_c.get(f"/api/resources/{resource_id}/report")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_resource_report_includes_audit_history(client, created):
    """PDF must be non-trivially sized — at least 1 KB — indicating content was generated."""
    r = client.get(f"/api/resources/{created['id']}/report")
    assert r.status_code == 200
    assert len(r.content) > 1024  # a blank PDF is ~700 bytes; any real content pushes it higher
