"""Profile data taken from a verified Keycloak access token (ЛР №5, requirement 2.7).

The token is verified elsewhere (``shared.security``); this module only turns
its claims into the fields of a User Service profile.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from shared.errors import AuthenticationError, BusinessRuleError

USER_NAME_MIN = 2
USER_NAME_MAX = 100
EMAIL_MAX = 255


@dataclass(frozen=True)
class ProfileClaims:
    user_id: uuid.UUID
    email: str
    user_name: str

    @classmethod
    def from_token(cls, claims: Mapping[str, Any]) -> ProfileClaims:
        try:
            user_id = uuid.UUID(str(claims.get("sub")))
        except ValueError as error:
            raise AuthenticationError("The access token has no valid subject.") from error

        email = str(claims.get("email") or "").strip().lower()
        if not email or "@" not in email or len(email) > EMAIL_MAX:
            raise BusinessRuleError("The identity provider did not share a valid email address.")
        return cls(user_id=user_id, email=email, user_name=_profile_name(claims, email))


def _profile_name(claims: Mapping[str, Any], email: str) -> str:
    """``name`` -> ``preferred_username`` -> local part of the email, fitted to 2..100 characters."""
    for candidate in (claims.get("name"), claims.get("preferred_username"), email.split("@", 1)[0]):
        name = " ".join(str(candidate or "").split())[:USER_NAME_MAX].strip()
        if len(name) >= USER_NAME_MIN:
            return name
    return "User"
