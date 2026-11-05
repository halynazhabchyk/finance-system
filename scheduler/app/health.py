"""FastAPI health endpoint and readiness state."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status


@dataclass
class Readiness:
    rabbitmq_available: bool = False
    scheduler_running: bool = False

    @property
    def ready(self) -> bool:
        return self.rabbitmq_available and self.scheduler_running


def create_router(readiness: Readiness) -> APIRouter:
    router = APIRouter(prefix="/internal", tags=["system"])

    @router.get("/health")
    async def health() -> dict[str, str]:
        if not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scheduler dependencies are not ready.",
            )
        return {"status": "ok", "service": "scheduler"}

    return router
