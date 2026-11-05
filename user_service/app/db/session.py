import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


SERVICE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(SERVICE_ROOT / ".env")


def get_database_url() -> str:
    """Build the User Service PostgreSQL connection URL from environment."""
    user = os.getenv("USER_DB_USER")
    password = os.getenv("USER_DB_PASSWORD")
    database = os.getenv("USER_DB_NAME")
    host = os.getenv("USER_DB_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", os.getenv("USER_DB_PORT", "5432"))

    required = {
        "USER_DB_USER": user,
        "USER_DB_PASSWORD": password,
        "USER_DB_NAME": database,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    return URL.create(
        drivername="postgresql+psycopg",
        username=user,
        password=password,
        host=host,
        port=int(port),
        database=database,
    ).render_as_string(hide_password=False)


DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for User Service persistence models."""
