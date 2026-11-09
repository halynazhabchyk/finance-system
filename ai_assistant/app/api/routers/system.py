from fastapi import APIRouter


router = APIRouter(prefix="/internal", tags=["system"])


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "ai-assistant", "message": "AI Assistant is running"}


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
