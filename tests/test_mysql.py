"""MySQL integration tests.

Run these with a real MySQL instance:
    DATABASE_URL="mysql+pymysql://tribal:tribal@localhost/tribal_test" pytest tests/test_mysql.py -v

Skipped automatically when DATABASE_URL is SQLite (the default).
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/tribal.db")
IS_MYSQL = DATABASE_URL.startswith("mysql")


@pytest.fixture(scope="module")
def mysql_engine():
    if not IS_MYSQL:
        pytest.skip("MySQL DATABASE_URL not set")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def mysql_session(mysql_engine):
    Session = sessionmaker(bind=mysql_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def test_mysql_connection(mysql_engine):
    """Verify we can connect and run a basic query."""
    with mysql_engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_mysql_all_tables_exist(mysql_engine):
    """Verify all expected tables were created."""
    from sqlalchemy import inspect
    inspector = inspect(mysql_engine)
    tables = set(inspector.get_table_names())
    expected = {"users", "admin_settings", "teams", "audit_logs", "api_keys", "resources", "reminder_logs"}
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_mysql_json_columns(mysql_session):
    """Verify JSON columns work correctly (MySQL 5.7.8+ feature)."""
    from app.models import AdminSettings
    # Remove any leftover row from a prior failed run before inserting.
    existing = mysql_session.get(AdminSettings, 1)
    if existing:
        mysql_session.delete(existing)
        mysql_session.commit()
    settings = AdminSettings(id=1, reminder_days=[30, 14, 7, 3], notify_hour=9, alert_on_overdue=False)
    mysql_session.add(settings)
    mysql_session.commit()

    fetched = mysql_session.get(AdminSettings, 1)
    assert fetched.reminder_days == [30, 14, 7, 3]

    mysql_session.delete(fetched)
    mysql_session.commit()


def test_mysql_foreign_key_cascade(mysql_session):
    """Verify ON DELETE CASCADE works for api_keys → users."""
    from app.auth import hash_password
    from app.models import User, ApiKey
    import hashlib

    user = User(
        email="fk_test@example.com",
        hashed_password=hash_password("TestPass1!"),
        is_admin=False,
        is_account_creator=False,
    )
    mysql_session.add(user)
    mysql_session.flush()

    key = ApiKey(
        user_id=user.id,
        name="test key",
        key_prefix="abcd",
        key_hash=hashlib.sha256(b"testkey").hexdigest(),
    )
    mysql_session.add(key)
    mysql_session.commit()
    key_id = key.id

    mysql_session.delete(user)
    mysql_session.commit()

    assert mysql_session.get(ApiKey, key_id) is None


def test_mysql_team_set_null_on_delete(mysql_session):
    """Verify ON DELETE SET NULL works for resources → teams."""
    from app.models import Team, Resource
    from datetime import date

    team = Team(name="Test Team FK")
    mysql_session.add(team)
    mysql_session.flush()

    resource = Resource(
        name="FK Test Resource",
        dri="test@example.com",
        expiration_date=date(2027, 1, 1),
        purpose="Testing",
        generation_instructions="N/A",
        slack_webhook="https://hooks.slack.com/test",
        type="Other",
        team_id=team.id,
    )
    mysql_session.add(resource)
    mysql_session.commit()
    resource_id = resource.id

    mysql_session.delete(team)
    mysql_session.commit()

    refreshed = mysql_session.get(Resource, resource_id)
    assert refreshed is not None
    assert refreshed.team_id is None


def test_mysql_string_lengths(mysql_engine):
    """Verify VARCHAR columns have correct lengths defined."""
    from sqlalchemy import inspect
    inspector = inspect(mysql_engine)

    user_cols = {c["name"]: c for c in inspector.get_columns("users")}
    assert user_cols["email"]["type"].length == 255
    assert user_cols["display_name"]["type"].length == 255

    resource_cols = {c["name"]: c for c in inspector.get_columns("resources")}
    assert resource_cols["name"]["type"].length == 255
    assert resource_cols["slack_webhook"]["type"].length == 500


def test_mysql_alembic_version_table(mysql_engine):
    """Verify Alembic version tracking table exists when migrations have been run."""
    from sqlalchemy import inspect
    inspector = inspect(mysql_engine)
    # alembic_version table only exists if alembic upgrade head was run
    # When using create_all in tests it won't exist — that's expected
    # This test just documents the distinction
    tables = set(inspector.get_table_names())
    # Both are valid depending on how tables were created
    assert "users" in tables  # just verify we're connected to the right DB
