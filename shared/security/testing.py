"""Test doubles for token verification: test RSA keys and an in-memory JWKS."""

from __future__ import annotations

import json
import time
import uuid
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm

from shared.security.jwt import OidcSettings, TokenVerifier

TEST_ISSUER = "http://localhost:8080/auth/realms/finance"
TEST_KID = "test-key-1"
ALL_AUDIENCES = ("user-service", "budget-service", "report-service", "ai-assistant")
DEFAULT_SCOPES = ("users:read", "budgets:read", "reports:read", "assistant:chat")


@lru_cache(maxsize=4)
def rsa_key(name: str = "main") -> rsa.RSAPrivateKey:
    """Deterministic per name within a test run (generation is the slow part)."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks(*keys: tuple[str, rsa.RSAPrivateKey]) -> dict[str, Any]:
    keys = keys or ((TEST_KID, rsa_key()),)
    entries = []
    for kid, key in keys:
        entry = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        entry.update({"kid": kid, "use": "sig", "alg": "RS256"})
        entries.append(entry)
    return {"keys": entries}


class StaticJwkClient(PyJWKClient):
    """PyJWKClient whose 'download' returns a JWKS held in memory."""

    def __init__(self, jwk_set: dict[str, Any] | None = None) -> None:
        super().__init__("http://keycloak.test/certs", cache_keys=True, cache_jwk_set=True, lifespan=300)
        self.jwk_set = jwk_set or jwks()
        self.downloads = 0

    def fetch_data(self) -> Any:
        self.downloads += 1
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(self.jwk_set)
        return self.jwk_set


def make_settings(audience: str = "budget-service", issuer: str = TEST_ISSUER) -> OidcSettings:
    return OidcSettings(issuer=issuer, jwks_url="http://keycloak.test/certs", audience=audience)


def make_verifier(audience: str = "budget-service", jwk_client: StaticJwkClient | None = None) -> TokenVerifier:
    return TokenVerifier(make_settings(audience), jwk_client or StaticJwkClient())


_GENERATE = object()


def make_token(
    sub: uuid.UUID | str | None | object = _GENERATE,
    *,
    scopes: tuple[str, ...] | list[str] = DEFAULT_SCOPES,
    audience: tuple[str, ...] | list[str] | str = ALL_AUDIENCES,
    issuer: str = TEST_ISSUER,
    expires_in: int = 300,
    issued_at: int | None = None,
    key: rsa.RSAPrivateKey | None = None,
    kid: str = TEST_KID,
    algorithm: str = "RS256",
    **claims: Any,
) -> str:
    """Keycloak-like test token; a claim set to None is dropped."""
    now = issued_at if issued_at is not None else int(time.time())
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": list(audience) if not isinstance(audience, str) else audience,
        "sub": str(uuid.uuid4()) if sub is _GENERATE else (None if sub is None else str(sub)),
        "typ": "Bearer",
        "azp": "finance-swagger",
        "iat": now,
        "exp": now + expires_in,
        "scope": " ".join(scopes),
        "email": "user@example.com",
        "name": "Test User",
        "preferred_username": "test.user",
    }
    payload.update(claims)
    payload = {name: value for name, value in payload.items() if value is not None}
    if algorithm == "none":
        return jwt.encode(payload, None, algorithm="none", headers={"kid": kid})
    if algorithm.startswith("HS"):
        return jwt.encode(payload, "test-secret-key-with-at-least-32-bytes!", algorithm=algorithm, headers={"kid": kid})
    return jwt.encode(payload, key or rsa_key(), algorithm=algorithm, headers={"kid": kid})
