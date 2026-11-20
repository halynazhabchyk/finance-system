"""Database of the service: engine, sessions and the declarative base."""

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import DeclarativeBase

from shared.db import DatabaseSettings, create_session_factory

SERVICE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(SERVICE_ROOT / ".env")

DATABASE = DatabaseSettings.from_env("BUDGET")
engine, SessionLocal = create_session_factory(DATABASE)


def get_database_url() -> str:
    """Used by Alembic (migrations/env.py)."""
    return DATABASE.url


class Base(DeclarativeBase):
    """Declarative base for tables owned by Budget Service."""
