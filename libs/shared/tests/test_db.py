"""Database settings of a service: <PREFIX>_DB_* variables and the connection URL."""

import pytest

from shared.db import DatabaseSettings


@pytest.fixture
def budget_env(monkeypatch):
    for name in ("POSTGRES_PORT", "BUDGET_DB_PORT", "BUDGET_DB_HOST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BUDGET_DB_USER", "budget")
    monkeypatch.setenv("BUDGET_DB_PASSWORD", "p@ss/word")
    monkeypatch.setenv("BUDGET_DB_NAME", "budget_db")
    return monkeypatch


def test_settings_from_prefixed_variables(budget_env):
    settings = DatabaseSettings.from_env("BUDGET")

    assert (settings.user, settings.name, settings.host, settings.port) == ("budget", "budget_db", "localhost", 5432)


def test_password_is_escaped_in_url(budget_env):
    url = DatabaseSettings.from_env("BUDGET").url

    assert url.startswith("postgresql+psycopg://budget:")
    assert "p%40ss%2Fword" in url
    assert url.endswith("@localhost:5432/budget_db")


def test_postgres_port_wins_over_service_port(budget_env):
    budget_env.setenv("BUDGET_DB_PORT", "6000")
    assert DatabaseSettings.from_env("BUDGET").port == 6000

    budget_env.setenv("POSTGRES_PORT", "7000")
    assert DatabaseSettings.from_env("BUDGET").port == 7000


def test_missing_variables_are_listed(budget_env):
    budget_env.delenv("BUDGET_DB_PASSWORD")
    budget_env.delenv("BUDGET_DB_NAME")

    with pytest.raises(RuntimeError, match="BUDGET_DB_PASSWORD, BUDGET_DB_NAME"):
        DatabaseSettings.from_env("BUDGET")
