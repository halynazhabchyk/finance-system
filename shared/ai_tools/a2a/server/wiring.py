"""Pieces every A2A agent needs when it assembles its application.

* a lazily created language model (structured skills work without one);
* the JWT check used by ``BearerAuthMiddleware`` (through User Service).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import lru_cache

from shared.ai_tools.a2a.server.auth import TokenVerifier
from shared.ai_tools.config import LLMSettings
from shared.ai_tools.gateway.factory import ApiClientFactory
from shared.ai_tools.llm import LLMClient
from shared.ai_tools.llm.factory import create_llm_client

LLMFactory = Callable[[], LLMClient | None]


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def lazy_llm_factory(settings: LLMSettings | None, override: LLMClient | None = None) -> LLMFactory:
    """The model is created on first use and reused; ``None`` when no key is configured.

    ``override`` is the scripted model of tests.
    """

    @lru_cache
    def factory() -> LLMClient | None:
        if override is not None:
            return override
        return create_llm_client(settings) if settings else None

    return factory


def jwt_verifier(api_client_factory: ApiClientFactory) -> TokenVerifier:
    """Verify the caller's JWT with User Service before an A2A task is created."""

    async def verify(token: str) -> None:
        async with api_client_factory(token) as client:
            await client.verify_current_user()

    return verify
