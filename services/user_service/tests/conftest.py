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
