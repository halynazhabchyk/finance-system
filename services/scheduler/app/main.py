"""Scheduler FastAPI entrypoint."""

from app.runtime import create_app

app = create_app()
