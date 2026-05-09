"""Shared pytest configuration."""
import pytest

from app.auth import _reset_jwt_secret_cache


@pytest.fixture(autouse=True)
def _reset_jwt_cache():
    """Each test starts with a fresh JWT-secret cache.

    The cache is module-level so without this it would leak across tests
    (whose tmp DBs are created and dropped). Resetting forces every test
    to load/create the secret from its own DB on first use.
    """
    _reset_jwt_secret_cache()
    yield
    _reset_jwt_secret_cache()
