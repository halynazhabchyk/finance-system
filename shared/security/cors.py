"""CORS policy shared by the public HTTP services (ЛР №5, requirement 1).

Browsers block a script from reading a response of another origin unless the
response allows it. The policy is applied by FastAPI itself (``CORSMiddleware``),
not by the gateway, so every service answers the preflight on its own and
Traefik passes the headers through untouched.

* Allowed origins are an explicit list from ``CORS_ALLOWED_ORIGINS``; ``*`` is
  rejected at startup.
* Credentials (cookies) are not allowed: the access token travels in the
  ``Authorization`` header, which the browser never attaches on its own.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse, Response

logger = logging.getLogger(__name__)

CORS_ORIGINS_ENV = "CORS_ALLOWED_ORIGINS"
ALLOWED_METHODS: tuple[str, ...] = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
ALLOWED_HEADERS: tuple[str, ...] = ("Authorization", "Content-Type")
PREFLIGHT_MAX_AGE_SECONDS = 600


class CorsConfigurationError(ValueError):
    """``CORS_ALLOWED_ORIGINS`` contains a wildcard or a value that is not an origin."""


@dataclass(frozen=True)
class CorsSettings:
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> CorsSettings:
        return cls(allowed_origins=parse_allowed_origins(os.getenv(CORS_ORIGINS_ENV, "")))


def parse_allowed_origins(raw: str) -> tuple[str, ...]:
    """Comma-separated origins -> normalized tuple (``scheme://host[:port]``, no trailing slash)."""
    origins: list[str] = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        if "*" in origin:
            raise CorsConfigurationError(f"{CORS_ORIGINS_ENV} must list explicit origins; wildcards are not allowed.")
        parts = urlsplit(origin)
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.path or parts.query or parts.fragment:
            raise CorsConfigurationError(f"{CORS_ORIGINS_ENV}: '{origin}' is not an origin (expected scheme://host[:port]).")
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


class ExplicitOriginCORSMiddleware(CORSMiddleware):
    """Starlette's CORS, except that a preflight from a foreign origin gets no ``Access-Control-*`` at all.

    Starlette adds the allowed methods and headers to every preflight response,
    even a rejected one. The browser blocks it anyway (no ``Access-Control-Allow-Origin``),
    but a foreign origin should not learn the policy (requirement 1.6).
    """

    def preflight_response(self, request_headers: Headers) -> Response:
        if not self.is_allowed_origin(origin=request_headers["origin"]):
            return PlainTextResponse("Disallowed CORS origin", status_code=400, headers={"Vary": "Origin"})
        return super().preflight_response(request_headers)


def install_cors(app: FastAPI, settings: CorsSettings | None = None) -> None:
    """Add the shared CORS policy; call it after other middlewares so it stays outermost.

    The outermost position matters: error responses (401/403/404) produced inside
    the app also carry the CORS headers, so the browser shows the real status.
    """
    settings = settings or CorsSettings.from_env()
    if not settings.allowed_origins:
        logger.warning("cors_disabled reason=no_allowed_origins env=%s", CORS_ORIGINS_ENV)
    app.add_middleware(
        ExplicitOriginCORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=list(ALLOWED_METHODS),
        allow_headers=list(ALLOWED_HEADERS),
        allow_credentials=False,
        max_age=PREFLIGHT_MAX_AGE_SECONDS,
    )
    logger.info("cors_configured origins=%s", ",".join(settings.allowed_origins))
