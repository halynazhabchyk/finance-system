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
