"""Security / pentest tests.

These verify the defences added in response to prior pentest findings and
exercise authentication, authorization, SSRF, and input-validation paths.
"""
import socket
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import get_db
from app.main import app
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

    with Session() as db:
        db.add(User(email="admin@example.com", hashed_password=hash_password("Password1!"), is_admin=True, is_account_creator=True))
        db.add(User(email="member@example.com", hashed_password=hash_password("Password1!"), is_admin=False))
        db.commit()

    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        assert r.status_code == 200
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def member_client(client):
    """A separate authenticated session for the non-admin user."""
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "member@example.com", "password": "Password1!"})
        assert r.status_code == 200
        yield c


def _public_getaddrinfo(hostname, port, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", port))]


# ── Auth middleware ──────────────────────────────────────────────────────────

def test_unauth_get_redirects_to_login(tmp_path):
    """Unauthenticated GET requests redirect to /login (303), they don't 401."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=False) as c:
            r = c.get("/api/resources/")
            assert r.status_code == 303
            assert r.headers["location"] == "/login"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_unauth_mutating_request_returns_401(tmp_path):
    """Unauthenticated non-GET requests return 401 JSON, not a redirect."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=False) as c:
            r = c.post("/api/resources/", json={})
            assert r.status_code == 401
            assert r.json() == {"detail": "Not authenticated"}

            r = c.delete("/api/resources/1")
            assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_exempt_paths_are_unauthenticated():
    """healthz, metrics, login, /static/ require no session."""
    with TestClient(app, follow_redirects=False) as c:
        for path in ("/healthz", "/metrics", "/login"):
            r = c.get(path)
            assert r.status_code == 200, f"Expected 200 for exempt path {path}, got {r.status_code}"


def test_tampered_session_cookie_rejected(tmp_path):
    """A garbage JWT cookie must not authenticate."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=False) as c:
            c.cookies.set("session", "not-a-valid-jwt")
            r = c.get("/api/resources/")
            assert r.status_code == 303  # redirected to login
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_bearer_with_non_tribal_prefix_rejected(client):
    """A Bearer token that doesn't match Tribal's key format should not authenticate."""
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/resources/", headers={"Authorization": "Bearer sk-something-else"})
        assert r.status_code in (401, 303)


# ── HTTPS-only URL validation (pentest fix) ──────────────────────────────────

@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.slack.com/services/X",
        "ftp://hooks.slack.com",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,<script>alert(1)</script>",
        "https://",  # missing host
        "://no-scheme",
    ],
)
def test_resource_create_rejects_non_https_slack_webhook(client, url):
    payload = {**SAMPLE, "slack_webhook": url}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 422


def test_resource_create_rejects_http_certificate_url(client):
    payload = {**SAMPLE, "certificate_url": "http://api.example.com"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 422


def test_resource_create_rejects_http_secret_manager_link(client):
    payload = {**SAMPLE, "secret_manager_link": "http://vault.example.com/secret"}
    r = client.post("/api/resources/", json=payload)
    assert r.status_code == 422


def test_resource_update_rejects_http_url(client):
    r = client.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    rid = r.json()["id"]

    r = client.put(
        f"/api/resources/{rid}",
        json={"slack_webhook": "http://hooks.slack.com/X"},
    )
    assert r.status_code == 422


def test_admin_settings_rejects_http_webhook(client):
    payload = {
        "reminder_days": [30, 14, 7, 3],
        "notify_hour": 9,
        "slack_webhook": "http://hooks.slack.com/admin",
    }
    r = client.put("/admin/settings", json=payload)
    assert r.status_code == 422


def test_webhook_test_rejects_http_url(client):
    r = client.post(
        "/api/resources/webhook-test",
        json={"webhook_url": "http://hooks.slack.com/X"},
    )
    assert r.status_code == 422


# ── SSRF guard (pentest fix) ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    "private_ip",
    [
        "127.0.0.1",        # loopback
        "10.0.0.1",         # RFC1918
        "192.168.1.1",      # RFC1918
        "172.16.0.1",       # RFC1918
        "169.254.169.254",  # link-local (cloud metadata!)
        "::1",              # IPv6 loopback
    ],
)
def test_cert_lookup_blocks_private_ips(client, monkeypatch, private_ip):
    """Cert-lookup endpoint must refuse to connect to private/internal addresses."""
    family = socket.AF_INET6 if ":" in private_ip else socket.AF_INET

    def fake_getaddrinfo(host, port, **kw):
        return [(family, socket.SOCK_STREAM, 6, "", (private_ip, port))]

    monkeypatch.setattr("app.cert_utils.socket.getaddrinfo", fake_getaddrinfo)
    r = client.post("/api/resources/cert-lookup", json={"endpoint": "internal.example.com"})
    assert r.status_code == 400
    assert "private" in r.json()["detail"].lower() or "internal" in r.json()["detail"].lower()


def test_webhook_test_blocks_private_ips(client, monkeypatch):
    """Webhook-test endpoint must refuse to POST to internal addresses."""
    monkeypatch.setattr(
        "app.cert_utils.socket.getaddrinfo",
        lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))],
    )
    r = client.post(
        "/api/resources/webhook-test",
        json={"webhook_url": "https://localhost-alias.example.com/x"},
    )
    assert r.status_code == 400
    assert "private" in r.json()["detail"].lower() or "internal" in r.json()["detail"].lower()


def test_admin_webhook_test_blocks_private_ips(client, monkeypatch):
    monkeypatch.setattr(
        "app.cert_utils.socket.getaddrinfo",
        lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", port))],
    )
    r = client.post(
        "/admin/webhook-test",
        json={"webhook_url": "https://metadata-alias.example.com/x"},
    )
    assert r.status_code == 400


# ── Cert upload size limit (pentest fix) ─────────────────────────────────────

def test_cert_upload_rejects_oversized_file(client):
    r = client.post("/api/resources/", json=SAMPLE)
    assert r.status_code == 201
    rid = r.json()["id"]

    # 64 KB + 1 byte (one over the limit)
    big_payload = b"-----BEGIN CERTIFICATE-----\n" + (b"A" * 65_537) + b"\n-----END CERTIFICATE-----\n"
    r = client.post(
        f"/api/resources/{rid}/certificate",
        files={"file": ("cert.pem", big_payload, "application/octet-stream")},
    )
    assert r.status_code == 413


# ── Resource restore audit log + auth (pentest fix) ──────────────────────────

def test_restore_resource_writes_audit(client):
    r = client.post("/api/resources/", json=SAMPLE)
    rid = r.json()["id"]

    with patch("app.routers.resources.send_deletion_notification", new=AsyncMock()):
        client.delete(f"/api/resources/{rid}")

    r = client.post(f"/admin/resources/{rid}/restore")
    assert r.status_code == 200
    assert r.json()["id"] == rid

    audit = client.get("/admin/audit-log").json()
    restore = [e for e in audit if e["action"] == "resource.restore"]
    assert restore, "Expected a resource.restore audit entry"
    assert restore[0]["resource_id"] == rid


def test_restore_endpoint_requires_auth(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=False) as anon:
            r = anon.post("/admin/resources/1/restore")
            assert r.status_code in (401, 303)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


# ── Admin authorization ──────────────────────────────────────────────────────

def test_non_admin_blocked_from_admin_endpoints(member_client):
    forbidden = [
        ("GET",    "/admin/settings"),
        ("GET",    "/admin/users"),
        ("GET",    "/admin/audit-log"),
        ("GET",    "/admin/resources/deleted"),
        ("GET",    "/admin/api-keys"),
        ("POST",   "/admin/teams"),
    ]
    for method, path in forbidden:
        r = member_client.request(method, path, json={"name": "x"})
        assert r.status_code == 403, f"{method} {path} expected 403, got {r.status_code}"


def test_cannot_delete_self(client):
    me = client.get("/auth/me").json()
    r = client.delete(f"/admin/users/{me['id']}")
    assert r.status_code == 400
    assert "own account" in r.json()["detail"].lower()


def test_cannot_demote_last_admin(client):
    """If only one admin remains, they cannot be demoted."""
    me = client.get("/auth/me").json()
    # Account creator can never lose admin — verify this path first
    r = client.put(f"/admin/users/{me['id']}/role?is_admin=false")
    assert r.status_code == 400


def test_audit_log_limit_enforced(client):
    """Limit query parameter must be bounded; absurd values are rejected."""
    r = client.get("/admin/audit-log?limit=0")
    assert r.status_code == 422
    r = client.get("/admin/audit-log?limit=10000")
    assert r.status_code == 422
    r = client.get("/admin/audit-log?limit=-1")
    assert r.status_code == 422
    # Within bounds works
    r = client.get("/admin/audit-log?limit=10")
    assert r.status_code == 200


# ── /api/keys/verify endpoint ────────────────────────────────────────────────

def test_keys_verify_with_valid_key(client):
    raw = client.post("/api/keys/", json={"name": "Verify Test"}).json()["full_key"]
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/keys/verify", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["owner"] == "admin@example.com"


def test_keys_verify_missing_bearer(client):
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/keys/verify")
        assert r.status_code in (401, 303)


def test_keys_verify_non_tribal_key(client):
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/keys/verify", headers={"Authorization": "Bearer ghp_not_a_tribal_key"})
        assert r.status_code in (400, 401, 303)


def test_keys_verify_revoked_key(client):
    create = client.post("/api/keys/", json={"name": "Revoked"}).json()
    raw, kid = create["full_key"], create["id"]
    client.delete(f"/api/keys/{kid}")
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.get("/api/keys/verify", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code in (401, 303)


# ── Provider identify endpoint ───────────────────────────────────────────────

def test_identify_known_key(client):
    r = client.post(
        "/api/resources/identify",
        json={"key": "ghp_" + "A" * 36, "introspect": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["matched"] is True
    assert body["provider"] == "GitHub"


def test_identify_no_match(client):
    r = client.post("/api/resources/identify", json={"key": "not-a-key", "introspect": False})
    assert r.status_code == 200
    assert r.json()["matched"] is False


def test_identify_with_explicit_provider(client):
    r = client.post(
        "/api/resources/identify",
        json={"key": "any-cloudflare-token", "provider": "Cloudflare", "introspect": False},
    )
    assert r.status_code == 200
    assert r.json()["matched"] is True


def test_identify_requires_auth():
    with TestClient(app, follow_redirects=False) as anon:
        r = anon.post("/api/resources/identify", json={"key": "x", "introspect": False})
        assert r.status_code in (401, 303)
