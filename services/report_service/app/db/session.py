"""Database of the service: engine, sessions and the declarative base."""

from sqlalchemy.orm import DeclarativeBase

from shared.db import create_session_factory

from app.core.config import get_settings

DATABASE = get_settings().database
engine, SessionLocal = create_session_factory(DATABASE)


def get_database_url() -> str:
    """Used by Alembic (migrations/env.py)."""
    return DATABASE.url


class Base(DeclarativeBase):
    """Declarative base for Report Service read-model tables."""
