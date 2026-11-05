from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings


class AuthService:
    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Optional[User]:
        """Busca el usuario por username (o email alternativo) y valida la contraseña con bcrypt."""
        ident = credentials.username.lower().strip()
        user = db.query(User).filter(User.username == ident).first()
        if not user and "@" in ident:
            user = db.query(User).filter(User.email == ident).first()

        if not user or not user.is_active:
            return None
        if not verify_password(credentials.password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        """Crea un nuevo usuario en la base de datos."""
        existing = db.query(User).filter(User.username == user_in.username.lower().strip()).first()
        if existing:
            raise ValueError("El nombre de usuario ya se encuentra registrado.")
        
        user = User(
            username=user_in.username.lower().strip(),
            email=user_in.email.lower().strip() if user_in.email else None,
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            is_superuser=user_in.is_superuser,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def init_first_superuser(db: Session) -> User:
        """Crea el superusuario inicial si la tabla de usuarios está vacía o si no existe."""
        superuser = db.query(User).filter(User.username == settings.FIRST_SUPERUSER_USERNAME.lower()).first()
        if not superuser:
            superuser = User(
                username=settings.FIRST_SUPERUSER_USERNAME.lower(),
                email=settings.FIRST_SUPERUSER_EMAIL.lower() if settings.FIRST_SUPERUSER_EMAIL else None,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                full_name=settings.FIRST_SUPERUSER_NAME,
                is_superuser=True,
                is_active=True,
            )
            db.add(superuser)
            db.commit()
            db.refresh(superuser)
        return superuser
