"""Expected failures of the assistant -> HTTP statuses with a client-safe ``detail``."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.ai_tools.config import ConfigurationError
from shared.ai_tools.gateway.client import AccountBlocked, AuthenticationFailed
from shared.ai_tools.gateway.errors import GatewayError
from shared.ai_tools.guardrails import GuardrailViolation
from shared.ai_tools.llm import LLMError, LLMRateLimitError, LLMUnavailableError

logger = logging.getLogger(__name__)

GUARDRAIL_STATUS = {
    "empty_message": 422,
    "message_too_long": 422,
}


async def _authentication_failed(_: Request, __: AuthenticationFailed) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid or expired access token."},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _account_blocked(_: Request, __: AccountBlocked) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": "The user account is blocked."})


async def _guardrail(_: Request, error: GuardrailViolation) -> JSONResponse:
    return JSONResponse(
        status_code=GUARDRAIL_STATUS.get(error.code, 400),
        content={"detail": error.user_message, "guardrail": error.code},
    )


async def _llm_error(_: Request, error: LLMError) -> JSONResponse:
    if isinstance(error, LLMRateLimitError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Ліміт запитів до мовної моделі вичерпано. Спробуйте пізніше."},
            headers={"Retry-After": "60"},
        )
    if isinstance(error, LLMUnavailableError):
        return JSONResponse(status_code=503, content={"detail": "Мовна модель тимчасово недоступна."})
    return JSONResponse(status_code=502, content={"detail": "Мовна модель відхилила запит."})


async def _gateway_error(_: Request, error: GatewayError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": error.llm_message})


async def _configuration_error(_: Request, error: ConfigurationError) -> JSONResponse:
    logger.error("assistant_misconfigured error=%s", error)
    return JSONResponse(status_code=503, content={"detail": "The assistant is not configured."})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationFailed, _authentication_failed)
    app.add_exception_handler(AccountBlocked, _account_blocked)
    app.add_exception_handler(GuardrailViolation, _guardrail)
    app.add_exception_handler(LLMError, _llm_error)
    app.add_exception_handler(GatewayError, _gateway_error)
    app.add_exception_handler(ConfigurationError, _configuration_error)
