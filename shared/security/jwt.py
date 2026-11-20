"""Verification of Keycloak access tokens: RS256 via JWKS, iss, aud, exp."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS: tuple[str, ...] = ("RS256",)
DEFAULT_ISSUER = "http://localhost:8080/auth/realms/finance"
DEFAULT_JWKS_URL = "http://keycloak:8080/auth/realms/finance/protocol/openid-connect/certs"
REQUIRED_CLAIMS = ("exp", "iat", "iss", "aud", "sub")


class InvalidToken(Exception):
    """The token cannot be trusted. ``reason`` goes to the log, never to the client."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    jwks_url: str
    audience: str
    leeway_seconds: int = 30
    jwks_cache_seconds: int = 300

    @classmethod
    def from_env(cls) -> OidcSettings:
        audience = os.getenv("OIDC_AUDIENCE", "").strip()
        if not audience:
            raise RuntimeError("OIDC_AUDIENCE must name this service (for example budget-service).")
        return cls(
            issuer=os.getenv("OIDC_ISSUER", DEFAULT_ISSUER).rstrip("/"),
            jwks_url=os.getenv("OIDC_JWKS_URL", DEFAULT_JWKS_URL),
            audience=audience,
            leeway_seconds=int(os.getenv("OIDC_LEEWAY_SECONDS", "30")),
            jwks_cache_seconds=int(os.getenv("OIDC_JWKS_CACHE_SECONDS", "300")),
        )


@dataclass(frozen=True)
class VerifiedToken:
    """Claims of a token that passed every check. ``user_id`` is the Keycloak ``sub``."""

    user_id: uuid.UUID
    scopes: frozenset[str]
    claims: dict[str, Any]
    raw: str = field(repr=False)  # forwarded unchanged to other services, never logged

    def has_scopes(self, required: list[str] | tuple[str, ...]) -> bool:
        return set(required) <= self.scopes

    def missing_scopes(self, required: list[str] | tuple[str, ...]) -> list[str]:
        return [scope for scope in required if scope not in self.scopes]


class TokenVerifier:
    """One instance per process (shares the JWKS cache)."""

    def __init__(self, settings: OidcSettings, jwk_client: PyJWKClient | None = None) -> None:
        self.settings = settings
        self._jwk_client = jwk_client or PyJWKClient(
            settings.jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=settings.jwks_cache_seconds,
            timeout=5,
        )

    def verify(self, token: str) -> VerifiedToken:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise InvalidToken("malformed") from error
        if header.get("alg") not in ALLOWED_ALGORITHMS:
            raise InvalidToken(f"algorithm_not_allowed:{header.get('alg')}")
        if not header.get("kid"):
            raise InvalidToken("missing_kid")

        try:
            signing_key = self._jwk_client.get_signing_key(header["kid"])
        except jwt.PyJWKClientConnectionError as error:
            raise InvalidToken("jwks_unavailable") from error
        except jwt.PyJWKClientError as error:
            raise InvalidToken("unknown_kid") from error

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                leeway=self.settings.leeway_seconds,
                options={"require": list(REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as error:
            raise InvalidToken("expired") from error
        except jwt.ImmatureSignatureError as error:
            raise InvalidToken("not_yet_valid") from error
        except jwt.InvalidAudienceError as error:
            raise InvalidToken("wrong_audience") from error
        except jwt.InvalidIssuerError as error:
            raise InvalidToken("wrong_issuer") from error
        except jwt.InvalidSignatureError as error:
            raise InvalidToken("bad_signature") from error
        except jwt.MissingRequiredClaimError as error:
            raise InvalidToken(f"missing_claim:{error.claim}") from error
        except jwt.InvalidTokenError as error:
            raise InvalidToken("invalid") from error

        if claims.get("typ", "Bearer") != "Bearer":
            raise InvalidToken(f"not_an_access_token:{claims.get('typ')}")
        try:
            user_id = uuid.UUID(str(claims["sub"]))
        except ValueError as error:
            raise InvalidToken("subject_not_uuid") from error

        scopes = frozenset(str(claims.get("scope", "")).split())
        return VerifiedToken(user_id=user_id, scopes=scopes, claims=claims, raw=token)
