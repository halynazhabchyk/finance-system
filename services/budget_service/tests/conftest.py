import os

import pytest


os.environ.setdefault("BUDGET_DB_NAME", "budget_service_test")
os.environ.setdefault("BUDGET_DB_USER", "budget_service_test")
os.environ.setdefault("BUDGET_DB_PASSWORD", "test-password")
os.environ.setdefault("BUDGET_DB_HOST", "localhost")
os.environ.setdefault("CONSUL_ENABLED", "false")
os.environ.setdefault("OIDC_AUDIENCE", "budget-service")  # tests use test keys


class FakeSession:
    """In-memory stand-in for a SQLAlchemy session used by service code."""

    def __init__(self):
        self.added = []
        self.deleted = []
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, item):
        self.added.append(item)

    def delete(self, item):
        self.deleted.append(item)

    def execute(self, statement):
        self.executed.append(statement)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, item):
        pass


@pytest.fixture
def db():
    return FakeSession()


@pytest.fixture
def session_factory():
    """Factory that records every session it opens (for multi-transaction code)."""
    sessions = []

    def factory():
        session = FakeSession()
        sessions.append(session)
        return session

    factory.sessions = sessions
    return factory


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def as_user():
    """Override authentication and the DB session for route tests; cleaned up afterwards."""
    from app.api.dependencies import get_current_user, get_db
    from app.main import app

    def override(user_id):
        app.dependency_overrides[get_current_user] = lambda: user_id
        app.dependency_overrides[get_db] = lambda: iter([object()])

    yield override
    app.dependency_overrides.clear()
