import os

import pytest


os.environ.setdefault("USER_DB_NAME", "user_service_test")
os.environ.setdefault("USER_DB_USER", "user_service_test")
os.environ.setdefault("USER_DB_PASSWORD", "test-password")
os.environ.setdefault("USER_DB_HOST", "localhost")
os.environ.setdefault("CONSUL_ENABLED", "false")
os.environ.setdefault("OIDC_AUDIENCE", "user-service")  # tests use test keys


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main

    return TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh_settings():
    """Settings are cached per process; every test starts from the current environment."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
