"""Health endpoint of the Scheduler."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.readiness import Readiness


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
