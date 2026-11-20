"""Shared CORS policy: explicit origins from CORS_ALLOWED_ORIGINS, no "*", no credentials."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def install_cors(app: FastAPI, settings: CorsSettings | None = None) -> None:
    """Add the shared CORS policy; call it last so it stays the outermost middleware."""
    settings = settings or CorsSettings.from_env()
    if not settings.allowed_origins:
        logger.warning("cors_disabled reason=no_allowed_origins env=%s", CORS_ORIGINS_ENV)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=list(ALLOWED_METHODS),
        allow_headers=list(ALLOWED_HEADERS),
        allow_credentials=False,
        max_age=PREFLIGHT_MAX_AGE_SECONDS,
    )
    logger.info("cors_configured origins=%s", ",".join(settings.allowed_origins))
