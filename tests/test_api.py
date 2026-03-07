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
