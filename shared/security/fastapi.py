"""FastAPI dependency: verifies the Bearer token; 401 if invalid, 403 if a scope is missing."""

# No "from __future__ import annotations": FastAPI must resolve Depends(scheme) at build time.
import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer, SecurityScopes

from shared.security.jwt import InvalidToken, OidcSettings, TokenVerifier, VerifiedToken

logger = logging.getLogger("security.token")

UNAUTHORIZED_DETAIL = "Invalid or missing access token."
FORBIDDEN_DETAIL = "The access token does not grant the required scope."


@lru_cache
def _process_verifier() -> TokenVerifier:
    return TokenVerifier(OidcSettings.from_env())


def get_token_verifier() -> TokenVerifier:
    """One verifier per process (shared JWKS cache). Tests override this dependency."""
    return _process_verifier()


def unauthorized(error: str | None = None) -> HTTPException:
    challenge = "Bearer" if error is None else f'Bearer error="{error}"'
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL, headers={"WWW-Authenticate": challenge})


def insufficient_scope(missing: list[str]) -> HTTPException:
    challenge = f'Bearer error="insufficient_scope", scope="{" ".join(missing)}"'
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_DETAIL, headers={"WWW-Authenticate": challenge})


def bearer_token_dependency(scheme: OAuth2AuthorizationCodeBearer) -> Callable[..., VerifiedToken]:
    """Build the dependency for a service; ``scheme`` must use ``auto_error=False``."""

    def verified_token(
        security_scopes: SecurityScopes,
        token: Annotated[str | None, Depends(scheme)],
        verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    ) -> VerifiedToken:
        if not token:
            logger.info("token_rejected reason=missing")
            raise unauthorized()
        try:
            verified = verifier.verify(token)
        except InvalidToken as error:
            logger.warning("token_rejected reason=%s", error.reason)
            raise unauthorized("invalid_token") from error

        missing = verified.missing_scopes(security_scopes.scopes)
        if missing:
            logger.warning("token_rejected reason=insufficient_scope sub=%s missing=%s", verified.user_id, ",".join(missing))
            raise insufficient_scope(missing)
        logger.info(
            "token_verified sub=%s aud=%s scopes=%s",
            verified.user_id,
            verifier.settings.audience,
            ",".join(sorted(verified.scopes)),
        )
        return verified

    return verified_token
