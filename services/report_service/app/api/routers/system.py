from fastapi import APIRouter, Depends

from shared.db import database_available
from shared.errors import ServiceUnavailableError

from app.db.session import engine


router = APIRouter(prefix="/internal", tags=["system"])


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "report-service", "message": "Report Service is running"}


def check_database() -> None:
    """Readiness: without its database the instance must leave the Consul/Traefik rotation (503)."""
    if not database_available(engine):
        raise ServiceUnavailableError("The Report Service database is unavailable.")


@router.get("/health", dependencies=[Depends(check_database)])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
