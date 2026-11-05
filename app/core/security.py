from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import bcrypt
import jwt
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def get_password_hash(password: str) -> str:
    """Genera hash bcrypt seguro para la contraseña."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña plana contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None
) -> str:
    """Genera un token JWT firmado."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        to_encode.update(extra_claims)
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica y valida un token JWT."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None


def get_token_from_request(
    request: Request,
    bearer_token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[str]:
    """Obtiene el token JWT del header Authorization o de la cookie HTTPOnly."""
    if bearer_token:
        return bearer_token
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return None


def get_current_user_optional(
    token: Optional[str] = Depends(get_token_from_request),
    db: Session = Depends(get_db)
):
    """Devuelve el usuario actual si el token es válido, o None si no hay sesión."""
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def get_current_user(
    request: Request,
    user = Depends(get_current_user_optional)
):
    """Exige usuario autenticado. Si es HTML redirige o retorna 401."""
    if not user:
        # Si la petición acepta HTML (Navegador), levantamos excepción especial o 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
