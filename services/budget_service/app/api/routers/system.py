from fastapi import APIRouter


router = APIRouter(prefix="/internal", tags=["system"])


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "budget-service", "message": "Budget Service is running"}


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
