"""Tests for /auth/* endpoints: register, login, logout, /me."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, User


@pytest.fixture
def empty_db(tmp_path):
    """Fresh DB with no users — useful for testing first-user-is-admin behaviour."""
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
    yield Session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seeded_db(tmp_path):
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
    with Session() as db:
        db.add(User(
            email="alice@example.com",
            hashed_password=hash_password("Password1!"),
            display_name="Alice",
            is_admin=True,
            is_account_creator=True,
        ))
        db.commit()
    yield Session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# ── Register ─────────────────────────────────────────────────────────────────

def test_register_first_user_becomes_admin(empty_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/register", json={
            "email": "first@example.com",
            "password": "Password1!",
            "display_name": "First User",
        })
        assert r.status_code == 201
        # Verify their profile reports is_admin
        r2 = c.get("/auth/me")
        assert r2.status_code == 200
        body = r2.json()
        assert body["is_admin"] is True
        assert body["is_account_creator"] is True


def test_register_second_user_is_not_admin(empty_db):
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/register", json={"email": "first@example.com", "password": "Password1!"})

    # Register a second user from a brand-new client (so we don't reuse first user's cookie)
    with TestClient(app, follow_redirects=False) as c2:
        r = c2.post("/auth/register", json={"email": "second@example.com", "password": "Password1!"})
        assert r.status_code == 201
        me = c2.get("/auth/me").json()
        assert me["is_admin"] is False
        assert me["is_account_creator"] is False


def test_register_email_normalized_to_lowercase(empty_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/register", json={
            "email": "MixedCase@EXAMPLE.com",
            "password": "Password1!",
        })
        assert r.status_code == 201
        assert r.json()["email"] == "mixedcase@example.com"


def test_register_duplicate_email_rejected(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/register", json={
            "email": "alice@example.com",
            "password": "Password1!",
        })
        assert r.status_code == 409


@pytest.mark.parametrize(
    "password",
    [
        "short1!",       # too short
        "passwordnodigit!",  # no digit
        "Password123",   # no special char
    ],
)
def test_register_password_requirements(empty_db, password):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/register", json={
            "email": "user@example.com",
            "password": password,
        })
        assert r.status_code == 422


def test_register_invalid_email(empty_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/register", json={
            "email": "not-an-email",
            "password": "Password1!",
        })
        assert r.status_code == 422


# ── Login ────────────────────────────────────────────────────────────────────

def test_login_success_sets_cookie(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "alice@example.com", "password": "Password1!"})
        assert r.status_code == 200
        assert "session" in c.cookies


def test_login_email_case_insensitive(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "ALICE@example.com", "password": "Password1!"})
        assert r.status_code == 200


def test_login_wrong_password_rejected(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "alice@example.com", "password": "Wrong!1"})
        assert r.status_code == 401


def test_login_unknown_user_rejected(seeded_db):
    """Unknown users return the same 401 as known-but-wrong-password — no enumeration."""
    with TestClient(app, follow_redirects=False) as c:
        r = c.post("/auth/login", json={"email": "ghost@example.com", "password": "Password1!"})
        assert r.status_code == 401
        # Same generic error message for unknown vs. wrong-password
        assert "incorrect" in r.json()["detail"].lower()


# ── Logout ───────────────────────────────────────────────────────────────────

def test_logout_clears_cookie(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "alice@example.com", "password": "Password1!"})
        assert "session" in c.cookies
        r = c.post("/auth/logout")
        assert r.status_code == 200
        # FastAPI delete_cookie sends a Set-Cookie that expires the value
        assert "session" not in c.cookies or c.cookies.get("session") in (None, "")


# ── /auth/me ─────────────────────────────────────────────────────────────────

def test_me_returns_profile(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "alice@example.com", "password": "Password1!"})
        r = c.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "alice@example.com"
        assert r.json()["display_name"] == "Alice"


def test_me_unauth_redirects(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        r = c.get("/auth/me")
        # /auth/* is exempt from middleware so the dependency raises 401
        assert r.status_code == 401


def test_me_patch_valid_timezone(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "alice@example.com", "password": "Password1!"})
        r = c.patch("/auth/me", json={"timezone": "America/New_York"})
        assert r.status_code == 200
        assert r.json()["timezone"] == "America/New_York"


def test_me_patch_invalid_timezone_rejected(seeded_db):
    with TestClient(app, follow_redirects=False) as c:
        c.post("/auth/login", json={"email": "alice@example.com", "password": "Password1!"})
        r = c.patch("/auth/me", json={"timezone": "Mars/Olympus_Mons"})
        assert r.status_code == 422
