"""Tests for TLS certificate expiry lookup."""
import socket
import ssl
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cert_utils import fetch_cert_expiry_from_endpoint
from app.main import app
from app.auth import hash_password
from app.database import get_db
from app.models import Base, User


# ── Fixtures ──────────────────────────────────────────────────────────────────

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

    with Session() as db:
        user = User(email="admin@example.com", hashed_password=hash_password("Password1!"), is_admin=True)
        db.add(user)
        db.commit()

    with TestClient(app) as c:
        c.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        yield c

    app.dependency_overrides.clear()


# ── Unit tests: fetch_cert_expiry_from_endpoint ────────────────────────────────

def test_cert_expiry_real_network():
    """Connect to google.com and confirm a future expiry date is returned."""
    expiry = fetch_cert_expiry_from_endpoint("google.com")
    assert expiry is not None
    assert isinstance(expiry, date)
    assert expiry > date.today(), "google.com cert should not already be expired"


def test_cert_expiry_accepts_https_url():
    """Full https:// URL is parsed correctly."""
    expiry = fetch_cert_expiry_from_endpoint("https://google.com")
    assert expiry is not None
    assert isinstance(expiry, date)


def test_cert_expiry_accepts_host_port():
    """host:port format is parsed correctly."""
    expiry = fetch_cert_expiry_from_endpoint("google.com:443")
    assert expiry is not None
    assert isinstance(expiry, date)


def test_cert_expiry_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.cert_utils.socket.create_connection",
        lambda *a, **kw: (_ for _ in ()).throw(socket.timeout()),
    )
    with pytest.raises(socket.timeout):
        fetch_cert_expiry_from_endpoint("unreachable.internal")


def test_cert_expiry_bad_hostname(monkeypatch):
    monkeypatch.setattr(
        "app.cert_utils.socket.create_connection",
        lambda *a, **kw: (_ for _ in ()).throw(socket.gaierror("Name or service not known")),
    )
    with pytest.raises(socket.gaierror):
        fetch_cert_expiry_from_endpoint("not-a-real-host.invalid")


def test_cert_expiry_invalid_endpoint():
    with pytest.raises(ValueError, match="hostname"):
        fetch_cert_expiry_from_endpoint("https://")


# ── API endpoint tests: POST /api/resources/cert-lookup ───────────────────────

def test_cert_lookup_endpoint_success(client):
    """API returns expiration_date when lookup succeeds."""
    mock_date = date(2026, 12, 31)
    with patch("app.routers.resources.fetch_cert_expiry_from_endpoint", return_value=mock_date):
        r = client.post("/api/resources/cert-lookup", json={"endpoint": "google.com"})
    assert r.status_code == 200
    assert r.json()["expiration_date"] == "2026-12-31"


def test_cert_lookup_endpoint_timeout(client):
    """API returns 400 with a helpful message on timeout."""
    with patch(
        "app.routers.resources.fetch_cert_expiry_from_endpoint",
        side_effect=socket.timeout(),
    ):
        r = client.post("/api/resources/cert-lookup", json={"endpoint": "slow.internal"})
    assert r.status_code == 400
    assert "timed out" in r.json()["detail"].lower()


def test_cert_lookup_endpoint_bad_hostname(client):
    """API returns 400 on DNS resolution failure."""
    with patch(
        "app.routers.resources.fetch_cert_expiry_from_endpoint",
        side_effect=socket.gaierror("Name or service not known"),
    ):
        r = client.post("/api/resources/cert-lookup", json={"endpoint": "not-real.invalid"})
    assert r.status_code == 400
    assert "resolve" in r.json()["detail"].lower()


def test_cert_lookup_endpoint_requires_auth():
    """Endpoint is not accessible without authentication."""
    with TestClient(app) as c:
        r = c.post("/api/resources/cert-lookup", json={"endpoint": "google.com"})
    assert r.status_code in (401, 303)
