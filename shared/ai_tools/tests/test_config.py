"""Settings come from environment variables; the API key is required and never printed."""

import pytest

from shared.ai_tools.config import AgentLimits, ConfigurationError, GatewaySettings, LLMSettings
from shared.ai_tools.llm.factory import create_llm_client


@pytest.fixture
def llm_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-value-123")
    monkeypatch.setenv("LLM_MODEL", "gemini-test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    monkeypatch.delenv("LLM_MAX_OUTPUT_TOKENS", raising=False)


def test_llm_settings_read_from_env_and_hide_key(llm_env):
    settings = LLMSettings.from_env()

    assert settings.provider == "gemini"
    assert settings.model == "gemini-test"
    assert settings.temperature == 0.0
    assert settings.max_output_tokens == 1024
    assert settings.api_key.get_secret_value() == "secret-value-123"
    assert "secret-value-123" not in repr(settings)
    assert "secret-value-123" not in str(settings)


def test_missing_api_key_is_a_configuration_error(llm_env, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "  ")
    with pytest.raises(ConfigurationError, match="LLM_API_KEY"):
        LLMSettings.from_env()


def test_missing_model_is_a_configuration_error(llm_env, monkeypatch):
    monkeypatch.delenv("LLM_MODEL")
    with pytest.raises(ConfigurationError, match="LLM_MODEL"):
        LLMSettings.from_env()


@pytest.mark.parametrize("name,value", [("LLM_MAX_OUTPUT_TOKENS", "0"), ("LLM_MAX_OUTPUT_TOKENS", "abc"), ("LLM_TEMPERATURE", "5")])
def test_invalid_numbers_are_rejected(llm_env, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError):
        LLMSettings.from_env()


def test_agent_limits_and_gateway_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_TOOL_ITERATIONS", "3")
    monkeypatch.setenv("AGENT_MAX_TOKENS_PER_REQUEST", "5000")
    monkeypatch.setenv("GATEWAY_URL", "http://traefik/")

    assert AgentLimits.from_env().max_tool_iterations == 3
    assert AgentLimits.from_env().max_tokens_per_request == 5000
    assert GatewaySettings.from_env().base_url == "http://traefik"


def test_factory_builds_gemini_adapter_and_rejects_unknown_provider(llm_env, monkeypatch):
    from shared.ai_tools.llm.gemini import GeminiLLMClient

    assert isinstance(create_llm_client(LLMSettings.from_env()), GeminiLLMClient)

    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    with pytest.raises(ConfigurationError, match="Unsupported"):
        create_llm_client(LLMSettings.from_env())


def test_only_the_adapter_imports_the_provider_sdk():
    """Provider-specific code is isolated in llm/gemini.py (requirement 1.2)."""
    from pathlib import Path

    package = Path(__file__).resolve().parents[1]
    offenders = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if "tests" not in path.parts
        and path.name != "gemini.py"
        and ("from google" in path.read_text(encoding="utf-8") or "import google" in path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_thinking_level_is_optional_and_normalized(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-value-123")
    monkeypatch.setenv("LLM_MODEL", "gemini-test")
    monkeypatch.delenv("LLM_THINKING_LEVEL", raising=False)
    assert LLMSettings.from_env().thinking_level is None

    monkeypatch.setenv("LLM_THINKING_LEVEL", " minimal ")
    assert LLMSettings.from_env().thinking_level == "MINIMAL"


def test_invalid_thinking_level_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret-value-123")
    monkeypatch.setenv("LLM_MODEL", "gemini-test")
    monkeypatch.setenv("LLM_THINKING_LEVEL", "extreme")
    with pytest.raises(ConfigurationError, match="LLM_THINKING_LEVEL"):
        LLMSettings.from_env()
