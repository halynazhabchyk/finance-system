"""Profile created at the first sign-in from the Keycloak token claims (ЛР №5, requirement 2.7)."""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from shared.errors import AuthenticationError, BusinessRuleError, ConflictError

SUB = uuid.UUID("05d32d26-2657-4042-aa14-088b89b43bee")


def claims(**overrides):
    base = {"sub": str(SUB), "email": "Halyna@Example.com", "name": "Halyna Zh", "preferred_username": "halyna"}
    base.update(overrides)
    return base


class FakeDb:
    def __init__(self, fail_commit=False):
        self.fail_commit = fail_commit
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        if self.fail_commit:
            raise IntegrityError("insert", {}, Exception("duplicate key"))
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, item):
        pass


@pytest.fixture
def repo(monkeypatch):
    from app.repositories import users as repository

    store = {"by_id": {}, "by_email": {}, "created": []}

    def create(db, *, user_id, user_name, email):
        user = SimpleNamespace(user_id=user_id, user_name=user_name, email=email, is_active=True)
        store["created"].append(user)
        return user

    monkeypatch.setattr(repository, "get_by_id", lambda db, user_id: store["by_id"].get(user_id))
    monkeypatch.setattr(repository, "get_by_email", lambda db, email: store["by_email"].get(email))
    monkeypatch.setattr(repository, "create", create)
    return store


def test_claims_map_to_profile_fields():
    from app.services.provisioning import ProfileClaims

    profile = ProfileClaims.from_token(claims())

    assert profile.user_id == SUB  # user_id = sub
    assert profile.email == "halyna@example.com"
    assert profile.user_name == "Halyna Zh"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"name": None}, "halyna"),
        ({"name": " ", "preferred_username": "x"}, "halyna"),  # local part of the normalized email
        ({"name": "A" * 150}, "A" * 100),
    ],
)
def test_profile_name_falls_back_and_fits_limits(overrides, expected):
    from app.services.provisioning import ProfileClaims

    assert ProfileClaims.from_token(claims(**overrides)).user_name == expected


def test_token_without_valid_subject_or_email_is_rejected():
    from app.services.provisioning import ProfileClaims

    with pytest.raises(AuthenticationError):
        ProfileClaims.from_token(claims(sub="not-a-uuid"))
    with pytest.raises(BusinessRuleError):
        ProfileClaims.from_token(claims(email=None))


def test_first_sign_in_creates_profile(repo):
    from app.services.provisioning import ProfileClaims
    from app.services.user_service import get_or_create_profile

    db = FakeDb()
    user = get_or_create_profile(db, ProfileClaims.from_token(claims()))

    assert user.user_id == SUB
    assert user.email == "halyna@example.com"
    assert len(repo["created"]) == 1
    assert db.commits == 1


def test_next_sign_in_reuses_profile(repo):
    from app.services.provisioning import ProfileClaims
    from app.services.user_service import get_or_create_profile

    existing = SimpleNamespace(user_id=SUB, user_name="Old name", email="halyna@example.com")
    repo["by_id"][SUB] = existing

    assert get_or_create_profile(FakeDb(), ProfileClaims.from_token(claims())) is existing
    assert repo["created"] == []


def test_email_of_another_profile_is_a_conflict(repo):
    from app.services.provisioning import ProfileClaims
    from app.services.user_service import get_or_create_profile

    repo["by_email"]["halyna@example.com"] = SimpleNamespace(user_id=uuid.uuid4())

    with pytest.raises(ConflictError):
        get_or_create_profile(FakeDb(), ProfileClaims.from_token(claims()))
    assert repo["created"] == []


def test_concurrent_first_requests_return_the_profile_created_by_the_other(repo, monkeypatch):
    from app.repositories import users as repository
    from app.services.provisioning import ProfileClaims
    from app.services.user_service import get_or_create_profile

    winner = SimpleNamespace(user_id=SUB, user_name="Halyna Zh", email="halyna@example.com")
    lookups = iter([None, winner])
    monkeypatch.setattr(repository, "get_by_id", lambda db, user_id: next(lookups))
    db = FakeDb(fail_commit=True)

    assert get_or_create_profile(db, ProfileClaims.from_token(claims())) is winner
    assert db.rollbacks == 1
