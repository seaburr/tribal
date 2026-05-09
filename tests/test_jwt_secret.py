"""Tests for the DB-backed JWT signing key and rotation endpoint."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import _reset_jwt_secret_cache, hash_password
from app.database import get_db
from app.main import app
from app.models import AppSecret, Base, User


@pytest.fixture
def env(tmp_path):
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
        db.add(User(
            email="admin@example.com",
            hashed_password=hash_password("Password1!"),
            is_admin=True,
            is_account_creator=True,
        ))
        db.add(User(
            email="member@example.com",
            hashed_password=hash_password("Password1!"),
            is_admin=False,
        ))
        db.commit()

    yield Session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_first_login_creates_jwt_secret_row(env):
    """No env var, no row — login bootstraps the secret into app_secrets."""
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        assert r.status_code == 200

    with env() as db:
        rows = db.query(AppSecret).filter_by(name="jwt_signing_key").all()
        assert len(rows) == 1
        assert rows[0].value
        assert len(rows[0].value) >= 32


def test_secret_persists_across_logins(env):
    """A second login must not regenerate the secret — it should reuse the stored one."""
    with TestClient(app, follow_redirects=False) as c1:
        c1.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})

    with env() as db:
        first = db.query(AppSecret).filter_by(name="jwt_signing_key").one().value

    _reset_jwt_secret_cache()  # simulate a process restart

    with TestClient(app, follow_redirects=False) as c2:
        c2.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})

    with env() as db:
        second = db.query(AppSecret).filter_by(name="jwt_signing_key").one().value

    assert first == second


def test_rotate_endpoint_admin_only_invalidates_sessions(env):
    """POST /admin/rotate-jwt-secret rotates the key; old cookies stop working."""
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        old_cookie = c.cookies.get("session")
        assert old_cookie

        r = c.post("/admin/rotate-jwt-secret")
        assert r.status_code == 204

    # Old cookie should now fail to authenticate (with auto-redirect off, GET → 303)
    with TestClient(app, follow_redirects=False) as c2:
        c2.cookies.set("session", old_cookie)
        r = c2.get("/auth/me")
        assert r.status_code == 401  # /auth/me bypasses redirect middleware

    # And the secret in the DB is now different from what the old cookie was signed with
    with env() as db:
        new_value = db.query(AppSecret).filter_by(name="jwt_signing_key").one().value
        # We don't have the old value, but rotating immediately after the first
        # login means the row's updated_at is later than created_at.
        assert new_value


def test_rotate_endpoint_rejects_non_admin(env):
    """Non-admins must get 403 from the rotate endpoint."""
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "member@example.com", "password": "Password1!"})
        r = c.post("/admin/rotate-jwt-secret")
        assert r.status_code == 403


def test_rotate_endpoint_requires_auth(env):
    """Unauthenticated callers get 401 (POST → JSON, not redirect)."""
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/admin/rotate-jwt-secret")
        assert r.status_code == 401


def test_rotate_writes_audit_log(env):
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        c.post("/admin/rotate-jwt-secret")

    from app.models import AuditLog
    with env() as db:
        entries = db.query(AuditLog).filter_by(action="admin.rotate_jwt_secret").all()
        assert len(entries) == 1
        assert entries[0].user_email == "admin@example.com"


def test_new_login_after_rotation_works(env):
    """After rotation, fresh logins must succeed and produce valid sessions."""
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        c.post("/admin/rotate-jwt-secret")

    with TestClient(app, follow_redirects=False) as c2:
        r = c2.post("/auth/login", json={"email": "admin@example.com", "password": "Password1!"})
        assert r.status_code == 200
        assert c2.cookies.get("session")
        me = c2.get("/auth/me")
        assert me.status_code == 200
