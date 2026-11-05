from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.auth import TokenResponse
from app.services.auth_service import authenticate_user


router = APIRouter(prefix="/internal/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    return authenticate_user(
        db,
        email=form_data.username,
        password=form_data.password,
    )
