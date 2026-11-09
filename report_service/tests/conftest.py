import os
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("REPORT_DB_NAME", "report_service_test")
os.environ.setdefault("REPORT_DB_USER", "report_service_test")
os.environ.setdefault("REPORT_DB_PASSWORD", "test-password")
os.environ.setdefault("REPORT_DB_HOST", "localhost")
os.environ.setdefault("CONSUL_ENABLED", "false")


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main

    return TestClient(main.app)


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


@pytest.fixture
def consumer_env(monkeypatch):
    """ReportEventConsumer with fake session and repository; returns (module, session, calls)."""
    from app.workers import report_consumer

    session = FakeSession()
    calls = {"snapshot": [], "deleted": [], "refresh": [], "processed": [], "sessions": 0}
    processed_ids = set()

    def open_session():
        calls["sessions"] += 1
        return session

    def mark(db, event_id, *args, **kwargs):
        processed_ids.add(event_id)
        calls["processed"].append(event_id)

    repository = report_consumer.repository
    monkeypatch.setattr(report_consumer, "SessionLocal", open_session)
    monkeypatch.setattr(repository, "event_processed", lambda db, event_id: event_id in processed_ids)
    monkeypatch.setattr(
        repository,
        "apply_budget_snapshot",
        lambda db, event: calls["snapshot"].append(event["event_type"]),
    )
    monkeypatch.setattr(
        repository,
        "apply_budget_deleted",
        lambda db, event: calls["deleted"].append(event["event_type"]),
    )
    monkeypatch.setattr(
        repository,
        "refresh_reports",
        lambda db, refreshed_at, period_start, period_end: calls["refresh"].append(
            (refreshed_at, period_start, period_end)
        ),
    )
    monkeypatch.setattr(repository, "mark_event_processed", mark)
    return report_consumer, session, calls


@pytest.fixture
def replies(consumer_env, monkeypatch):
    """Captures ExpenseProcessed replies instead of publishing them to RabbitMQ."""
    module, _, _ = consumer_env
    published = []
    monkeypatch.setattr(module, "publish_event", published.append)
    return published
