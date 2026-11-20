import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


SERVICE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(SERVICE_ROOT / ".env")


def get_database_url() -> str:
    """Build the Budget Service database URL from environment variables."""
    user = os.getenv("BUDGET_DB_USER")
    password = os.getenv("BUDGET_DB_PASSWORD")
    database = os.getenv("BUDGET_DB_NAME")
    host = os.getenv("BUDGET_DB_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", os.getenv("BUDGET_DB_PORT", os.getenv("USER_DB_PORT", "5432")))
    required = {"BUDGET_DB_USER": user, "BUDGET_DB_PASSWORD": password, "BUDGET_DB_NAME": database}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
    return URL.create(
        "postgresql+psycopg", username=user, password=password, host=host,
        port=int(port), database=database,
    ).render_as_string(hide_password=False)


DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for tables owned by Budget Service."""
