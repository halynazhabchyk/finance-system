import os
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVICE_ROOT.parent
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["CONSUL_ENABLED"] = "false"
os.environ.setdefault("OIDC_AUDIENCE", "ai-assistant")  # ЛР №5: tests override the verifier with test keys
os.environ.setdefault("LLM_API_KEY", "test-key-not-real")
os.environ.setdefault("LLM_MODEL", "gemini-test")
os.environ.setdefault("GATEWAY_URL", "http://gateway.test")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def keycloak_test_keys():
    """ЛР №5: the assistant verifies tokens itself; tests use the test JWKS instead of Keycloak."""
    from app.main import app
    from shared.security.fastapi import get_token_verifier
    from shared.security.testing import make_verifier

    app.dependency_overrides[get_token_verifier] = lambda: make_verifier("ai-assistant")
    yield
    app.dependency_overrides.pop(get_token_verifier, None)
