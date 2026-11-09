"""Settings of the AI components, read from environment variables only."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from pydantic import SecretStr

logger = logging.getLogger(__name__)


class ConfigurationError(RuntimeError):
    """A required environment variable is missing or has an invalid value."""


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}.") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive, got {value}.")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}.") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be positive, got {value}.")
    return value


@dataclass(frozen=True)
class LLMSettings:
    """Connection to the language model. ``api_key`` is never printed (SecretStr)."""

    provider: str
    api_key: SecretStr = field(repr=False)
    model: str
    temperature: float
    max_output_tokens: int
    request_timeout_seconds: float
    # How much the model reasons before answering (hidden thinking tokens are billed as output).
    # None keeps the provider default.
    thinking_level: str | None = None

    @classmethod
    def from_env(cls) -> LLMSettings:
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError("LLM_API_KEY is not set.")
        model = os.getenv("LLM_MODEL", "").strip()
        if not model:
            raise ConfigurationError("LLM_MODEL is not set.")
        raw_temperature = os.getenv("LLM_TEMPERATURE", "0")
        try:
            temperature = float(raw_temperature)
        except ValueError as error:
            raise ConfigurationError("LLM_TEMPERATURE must be a number.") from error
        if not 0 <= temperature <= 2:
            raise ConfigurationError("LLM_TEMPERATURE must be between 0 and 2.")
        return cls(
            provider=os.getenv("LLM_PROVIDER", "gemini").strip().lower(),
            api_key=SecretStr(api_key),
            model=model,
            temperature=temperature,
            max_output_tokens=_positive_int("LLM_MAX_OUTPUT_TOKENS", 1024),
            request_timeout_seconds=_positive_float("LLM_REQUEST_TIMEOUT_SECONDS", 30.0),
            thinking_level=_thinking_level(),
        )


THINKING_LEVELS = frozenset({"MINIMAL", "LOW", "MEDIUM", "HIGH"})


def _thinking_level() -> str | None:
    """``LLM_THINKING_LEVEL``: empty means the provider default."""
    raw = os.getenv("LLM_THINKING_LEVEL", "").strip().upper()
    if not raw:
        return None
    if raw not in THINKING_LEVELS:
        raise ConfigurationError(
            f"LLM_THINKING_LEVEL must be one of {sorted(THINKING_LEVELS)}, got {raw!r}."
        )
    return raw


@dataclass(frozen=True)
class AgentLimits:
    """Guardrails of level 1: how much one user request may consume."""

    max_tool_iterations: int = 6
    max_tokens_per_request: int = 20000
    tool_result_max_chars: int = 4000
    user_message_max_chars: int = 2000

    @classmethod
    def from_env(cls) -> AgentLimits:
        return cls(
            max_tool_iterations=_positive_int("AGENT_MAX_TOOL_ITERATIONS", 6),
            max_tokens_per_request=_positive_int("AGENT_MAX_TOKENS_PER_REQUEST", 20000),
            tool_result_max_chars=_positive_int("TOOL_RESULT_MAX_CHARS", 4000),
            user_message_max_chars=_positive_int("USER_MESSAGE_MAX_CHARS", 2000),
        )


@dataclass(frozen=True)
class GatewaySettings:
    """Where the public REST API of the system is reachable (Traefik)."""

    base_url: str = "http://localhost:8080"
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> GatewaySettings:
        return cls(
            base_url=os.getenv("GATEWAY_URL", "http://localhost:8080").rstrip("/"),
            timeout_seconds=_positive_float("GATEWAY_TIMEOUT_SECONDS", 10.0),
        )


def optional_llm_settings() -> LLMSettings | None:
    """For components that also work without a model (A2A agents): ``None`` if LLM is not configured."""
    try:
        return LLMSettings.from_env()
    except ConfigurationError as error:
        logger.warning("llm_disabled reason=%s", error)
        return None
