from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token, get_current_user
from app.models.user import User
from app.schemas.auth import UserLogin, UserResponse, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["Autenticación"])


@router.post("/api/auth/login", response_model=TokenResponse)
def api_login(
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """Autentica al usuario, emite un token JWT y setea la cookie segura HTTPOnly."""
    user = AuthService.authenticate_user(db, credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas o usuario inactivo.",
        )
    
    access_token = create_access_token(subject=user.id)
    
    # Cookie HTTPOnly para navegación web segura y HTMX
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/api/auth/token")
def oauth2_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Endpoint compatible con OAuth2 Password Flow para Swagger UI Docs."""
    credentials = UserLogin(username=form_data.username, password=form_data.password)
    user = AuthService.authenticate_user(db, credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/api/auth/logout")
def api_logout(response: Response):
    """Elimina la cookie de sesión."""
    response.delete_cookie(key=settings.COOKIE_NAME)
    return {"message": "Sesión cerrada exitosamente."}


@router.get("/api/auth/me", response_model=UserResponse)
def api_get_me(current_user: User = Depends(get_current_user)):
    """Obtiene los datos del usuario autenticado."""
    return UserResponse.model_validate(current_user)
