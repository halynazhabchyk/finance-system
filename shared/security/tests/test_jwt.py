"""Token verification with test keys."""

import time
import uuid

import pytest

from shared.security.jwt import InvalidToken, OidcSettings
from shared.security.testing import (
    StaticJwkClient,
    jwks,
    make_token,
    make_verifier,
    rsa_key,
)


def reason_of(token: str, **verifier_kwargs) -> str:
    with pytest.raises(InvalidToken) as error:
        make_verifier(**verifier_kwargs).verify(token)
    return error.value.reason


def test_valid_token_gives_user_id_scopes_and_raw_token():
    sub = uuid.uuid4()
    token = make_token(sub, scopes=("budgets:read", "budgets:write"))

    verified = make_verifier().verify(token)

    assert verified.user_id == sub
    assert verified.scopes == {"budgets:read", "budgets:write"}
    assert verified.raw == token
    assert token not in repr(verified)  # the token never ends up in logs through repr()


def test_expired_token_is_rejected():
    assert reason_of(make_token(issued_at=int(time.time()) - 3600, expires_in=300)) == "expired"


def test_small_clock_skew_is_tolerated():
    token = make_token(issued_at=int(time.time()) - 310, expires_in=300)  # expired 10 s ago, leeway 30 s

    assert make_verifier().verify(token).user_id


def test_token_not_yet_valid_is_rejected():
    assert reason_of(make_token(nbf=int(time.time()) + 600)) == "not_yet_valid"


def test_signature_of_another_key_is_rejected():
    assert reason_of(make_token(key=rsa_key("attacker"))) == "bad_signature"


def test_wrong_issuer_is_rejected():
    assert reason_of(make_token(issuer="http://evil.example/realms/finance")) == "wrong_issuer"


def test_token_for_another_service_is_rejected():
    token = make_token(audience=("report-service",))

    assert reason_of(token, audience="budget-service") == "wrong_audience"


def test_alg_none_is_rejected():
    assert reason_of(make_token(algorithm="none")) == "algorithm_not_allowed:none"


def test_hs256_token_like_the_former_user_service_token_is_rejected():
    assert reason_of(make_token(algorithm="HS256")) == "algorithm_not_allowed:HS256"


def test_garbage_is_rejected():
    assert reason_of("not-a-jwt") == "malformed"


@pytest.mark.parametrize("claim", ["exp", "aud", "iss"])
def test_required_claims(claim):
    assert reason_of(make_token(**{claim: None})).startswith("missing_claim")


def test_subject_is_required():
    assert reason_of(make_token(None)) == "missing_claim:sub"


def test_id_token_is_not_accepted_as_access_token():
    assert reason_of(make_token(typ="ID")) == "not_an_access_token:ID"


def test_subject_must_be_a_uuid():
    assert reason_of(make_token("not-a-uuid")) == "subject_not_uuid"


def test_jwks_is_cached_between_requests():
    client = StaticJwkClient()
    verifier = make_verifier(jwk_client=client)

    for _ in range(3):
        verifier.verify(make_token())

    assert client.downloads == 1


def test_unknown_kid_triggers_one_more_download_for_rotated_keys():
    client = StaticJwkClient()
    verifier = make_verifier(jwk_client=client)
    verifier.verify(make_token())

    # Key rotation: new kid appears after the first download.
    client.jwk_set = jwks(("test-key-1", rsa_key()), ("rotated-key", rsa_key("rotated")))
    verified = verifier.verify(make_token(key=rsa_key("rotated"), kid="rotated-key"))

    assert verified.user_id
    assert client.downloads == 2


def test_kid_missing_from_jwks_even_after_refresh_is_rejected():
    assert reason_of(make_token(kid="ghost")) == "unknown_kid"


def test_settings_require_audience(monkeypatch):
    monkeypatch.delenv("OIDC_AUDIENCE", raising=False)
    with pytest.raises(RuntimeError):
        OidcSettings.from_env()

    monkeypatch.setenv("OIDC_AUDIENCE", "report-service")
    monkeypatch.setenv("OIDC_ISSUER", "http://localhost:8080/auth/realms/finance/")
    monkeypatch.setenv("OIDC_JWKS_URL", "http://keycloak:8080/auth/realms/finance/protocol/openid-connect/certs")
    settings = OidcSettings.from_env()
    assert settings.issuer == "http://localhost:8080/auth/realms/finance"  # public address for "iss"
    assert settings.jwks_url.startswith("http://keycloak:8080/")  # internal address for keys
    assert settings.audience == "report-service"
