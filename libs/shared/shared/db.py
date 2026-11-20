"""PostgreSQL connection of a service: settings from <PREFIX>_DB_* variables, engine and sessions.

Each service still owns its database (Database per Service); only this setup code is shared.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class DatabaseSettings:
    user: str
    password: str
    name: str
    host: str
    port: int

    @classmethod
    def from_env(cls, prefix: str) -> DatabaseSettings:
        """Read <PREFIX>_DB_USER/PASSWORD/NAME/HOST; port: POSTGRES_PORT, <PREFIX>_DB_PORT, 5432."""
        values = {key: os.getenv(f"{prefix}_DB_{key.upper()}") for key in ("user", "password", "name")}
        missing = [f"{prefix}_DB_{key.upper()}" for key, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        port = os.getenv("POSTGRES_PORT") or os.getenv(f"{prefix}_DB_PORT") or "5432"
        return cls(host=os.getenv(f"{prefix}_DB_HOST", "localhost"), port=int(port), **values)

    @property
    def url(self) -> str:
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        ).render_as_string(hide_password=False)


def create_session_factory(settings: DatabaseSettings) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(settings.url, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False)


def database_available(engine: Engine) -> bool:
    """Readiness probe: the database answers a trivial query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
