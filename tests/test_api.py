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
